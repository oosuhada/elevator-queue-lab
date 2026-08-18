from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.learning import (
    RewardWeights,
    evaluate_learned_policy,
    model_verdict,
    save_model_artifact,
    train_agent,
)
from app.demand import demand_contract


TRAIN_SCENARIOS = ("morning", "lunch", "normal", "evening", "shock")
HELD_OUT_SCENARIOS = ("morning", "lunch", "normal", "evening", "shock", "mixed_day")
ABLATION_GROUPS = ("eta", "load", "capacity", "age", "prepositioning")


def _seed_range(spec: str) -> tuple[int, ...]:
    values: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if end < start:
                raise ValueError("seed range end must be >= start")
            values.extend(range(start, end + 1))
        else:
            values.append(int(part))
    if not values:
        raise ValueError("at least one seed is required")
    return tuple(dict.fromkeys(values))


def _headline(evaluation: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for summary in evaluation["summaries"]:
        if summary["policy"] not in {"collective", "capr", "rl"}:
            continue
        rows.append(
            {
                "scenario": summary["scenario"],
                "policy": summary["policy"],
                "avg_wait": round(float(summary["metrics"]["avg_wait"]["mean"]), 4),
                "p95_wait": round(float(summary["metrics"]["p95_wait"]["mean"]), 4),
                "worst_floor_mean_wait": round(
                    float(summary["metrics"]["worst_floor_mean_wait"]["mean"]), 4
                ),
                "energy_proxy": round(float(summary["metrics"]["energy_proxy"]["mean"]), 4),
                "guardrail": summary["guardrail_classification"],
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the dependency-free M5 Dueling Double DQN and run held-out evaluation."
    )
    parser.add_argument("--training-seeds", default="1-6")
    parser.add_argument("--held-out-seeds", default="21-30")
    parser.add_argument("--training-seconds", type=int, default=120)
    parser.add_argument("--evaluation-seconds", type=int, default=180)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--agent-seed", type=int, default=2026)
    parser.add_argument(
        "--model-output",
        type=Path,
        default=ROOT / "models" / "m5-ddqn-baseline.json",
    )
    parser.add_argument(
        "--evidence-output",
        type=Path,
        default=ROOT / "evidence" / "m5-heldout-evaluation.json",
    )
    parser.add_argument(
        "--skip-ablations",
        action="store_true",
        help="useful only for a quick local smoke run",
    )
    args = parser.parse_args()

    training_seeds = _seed_range(args.training_seeds)
    held_out_seeds = _seed_range(args.held_out_seeds)
    overlap = sorted(set(training_seeds) & set(held_out_seeds))
    if overlap:
        raise SystemExit(f"training and held-out seeds must be disjoint; overlap={overlap}")

    reward_weights = RewardWeights()
    agent, training = train_agent(
        scenarios=TRAIN_SCENARIOS,
        seeds=training_seeds,
        episode_seconds=args.training_seconds,
        epochs=args.epochs,
        seed=args.agent_seed,
    )
    metadata = {
        **training,
        "demand_contract": demand_contract(),
        "algorithm": "dependency-free Dueling Double DQN",
        "common_random_numbers_in_evaluation": True,
        "held_out_scenarios": list(HELD_OUT_SCENARIOS),
        "held_out_passenger_seeds": list(held_out_seeds),
        "reward_weights": reward_weights.__dict__ if hasattr(reward_weights, "__dict__") else {
            "mean_wait": reward_weights.mean_wait,
            "tail_wait": reward_weights.tail_wait,
            "floor_gap": reward_weights.floor_gap,
            "capacity_miss": reward_weights.capacity_miss,
            "energy": reward_weights.energy,
            "served": reward_weights.served,
        },
        "checkpoint_selection": (
            "fixed final checkpoint from a predeclared deterministic training budget; "
            "held-out seeds are never used for checkpoint selection"
        ),
    }
    save_model_artifact(args.model_output, agent.online, metadata=metadata)

    evaluation = evaluate_learned_policy(
        agent.online,
        scenarios=HELD_OUT_SCENARIOS,
        seeds=held_out_seeds,
        seconds=args.evaluation_seconds,
    )
    verdict = model_verdict(evaluation)

    ablations: dict[str, object] = {}
    if not args.skip_ablations:
        for group in ABLATION_GROUPS:
            result = evaluate_learned_policy(
                agent.online,
                scenarios=HELD_OUT_SCENARIOS,
                seeds=held_out_seeds,
                seconds=args.evaluation_seconds,
                ablations=(group,),
            )
            ablations[group] = {
                "verdict": model_verdict(result),
                "headline": _headline(result),
            }

    payload = {
        "schema": "elevator-queue-lab.m5-research-evidence.v1",
        "demand_contract": demand_contract(),
        "training_contract": {
            "scenarios": list(TRAIN_SCENARIOS),
            "passenger_seeds": list(training_seeds),
            "seconds": args.training_seconds,
            "epochs": args.epochs,
            "agent_seed": args.agent_seed,
        },
        "held_out_contract": {
            "scenarios": list(HELD_OUT_SCENARIOS),
            "held_out_mixture": "mixed_day",
            "passenger_seeds": list(held_out_seeds),
            "seconds": args.evaluation_seconds,
            "disjoint_from_training": True,
        },
        "verdict": verdict,
        "headline": _headline(evaluation),
        "evaluation": evaluation,
        "ablations": ablations,
        "limitations": [
            "The neural baseline is intentionally dependency-free and small; it is not a tuned production RL stack.",
            "Synthetic traffic is not measured building telemetry.",
            "Parking uses the same scenario-aware hotspot contract as CAPR; the network learns dispatch selection, not a separate parking action.",
            "An M5 superiority claim is allowed only when every held-out scenario passes the existing M3 fairness/energy guardrail.",
        ],
    }
    args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "model": str(args.model_output),
                "evidence": str(args.evidence_output),
                "training_episodes": len(training["episodes"]),
                "gradient_steps": training["gradient_steps"],
                "verdict": verdict,
                "headline": _headline(evaluation),
            },
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
