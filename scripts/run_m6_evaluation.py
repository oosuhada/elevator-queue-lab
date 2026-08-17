from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.learning import evaluate_learned_policy, load_model_artifact, model_verdict


SCENARIOS = ("morning", "lunch", "normal", "evening", "shock", "mixed_day")


def _seed_range(spec: str) -> tuple[int, ...]:
    if "-" not in spec:
        values = tuple(int(part.strip()) for part in spec.split(",") if part.strip())
        if not values:
            raise ValueError("at least one held-out seed is required")
        return values
    start_text, end_text = spec.split("-", 1)
    start, end = int(start_text), int(end_text)
    if end < start:
        raise ValueError("seed range end must be >= start")
    return tuple(range(start, end + 1))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the fixed M5 checkpoint on the 30-seed M6 held-out release contract."
    )
    parser.add_argument("--held-out-seeds", default="21-50")
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument(
        "--model",
        type=Path,
        default=ROOT / "models" / "m5-ddqn-baseline.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evidence" / "m6-heldout-30seed.json",
    )
    args = parser.parse_args()

    held_out_seeds = _seed_range(args.held_out_seeds)
    if len(held_out_seeds) < 30:
        raise SystemExit("M6 release evaluation requires at least 30 held-out seeds")
    network, metadata = load_model_artifact(args.model)
    training_seeds = {int(seed) for seed in metadata.get("training_passenger_seeds", [])}
    overlap = sorted(training_seeds & set(held_out_seeds))
    if overlap:
        raise SystemExit(f"M6 held-out seeds overlap M5 training seeds: {overlap}")

    evaluation = evaluate_learned_policy(
        network,
        scenarios=SCENARIOS,
        seeds=held_out_seeds,
        seconds=args.seconds,
    )
    payload = {
        "schema": "elevator-queue-lab.m6-heldout-release.v1",
        "fixed_model": str(args.model.relative_to(ROOT)).replace("\\", "/"),
        "fixed_model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
        "checkpoint_selection": metadata.get("checkpoint_selection"),
        "training_passenger_seeds": sorted(training_seeds),
        "held_out_contract": {
            "scenarios": list(SCENARIOS),
            "passenger_seeds": list(held_out_seeds),
            "seed_count": len(held_out_seeds),
            "seconds": args.seconds,
            "disjoint_from_training": True,
            "mixed_day_was_unseen_in_training": True,
        },
        "verdict": model_verdict(evaluation),
        "evaluation": evaluation,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "model_sha256": payload["fixed_model_sha256"],
                "held_out_seed_count": len(held_out_seeds),
                "verdict": payload["verdict"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
