from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.simulator import ElevatorSimulation


POLICIES = ("legacy_sticky", "collective", "queue_aware")


def confidence95(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return 1.96 * stdev(values) / math.sqrt(len(values))


def run_experiment(scenario: str, seconds: int, seeds: int) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for policy in POLICIES:
        runs: list[dict[str, float | int]] = []
        for seed in range(1, seeds + 1):
            simulation = ElevatorSimulation(scenario=scenario, policy_name=policy, seed=seed)
            runs.append(simulation.run(seconds))
        waits = [float(run["avg_wait"]) for run in runs]
        p95s = [float(run["p95_wait"]) for run in runs]
        rows.append(
            {
                "policy": policy,
                "runs": len(runs),
                "avg_wait_mean": round(mean(waits), 3),
                "avg_wait_ci95_halfwidth": round(confidence95(waits), 3),
                "p95_wait_mean": round(mean(p95s), 3),
                "capacity_misses_mean": round(mean(float(run["missed_capacity"]) for run in runs), 3),
            }
        )
    return {
        "schema": "elevator-queue-lab.experiment.v1",
        "scenario": scenario,
        "seconds": seconds,
        "seeds": seeds,
        "common_seed_range": [1, seeds],
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="morning", choices=("morning", "lunch", "normal", "evening"))
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = run_experiment(args.scenario, args.seconds, args.seeds)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()

