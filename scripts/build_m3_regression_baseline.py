from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from check_regression_baseline import _trace_manifest_sha256


def build_baseline(matrix: dict[str, object], artifact_sha256: str) -> dict[str, object]:
    window = matrix["measurement_window"]
    scenario_matrix = matrix["scenario_matrix"]
    scenarios: dict[str, object] = {}
    seed_counts = {int(scenario["seeds"]) for scenario in scenario_matrix}
    if len(seed_counts) != 1:
        raise ValueError("all M3 scenarios must use the same seed count")
    for scenario in scenario_matrix:
        policies: dict[str, object] = {}
        raw_runs = scenario["raw_runs"]
        for policy in scenario["policies"]:
            policy_name = policy["policy"]
            avg_wait_summary = policy["metrics"]["avg_wait"]
            policy_runs = sorted(
                (row for row in raw_runs if row["policy"] == policy_name),
                key=lambda row: int(row["seed"]),
            )
            policies[policy["policy"]] = {
                "avg_wait": avg_wait_summary["mean"],
                "avg_wait_ci95_halfwidth": avg_wait_summary["ci95_halfwidth"],
                "avg_wait_min": avg_wait_summary["min"],
                "avg_wait_max": avg_wait_summary["max"],
                "avg_wait_seed_values": [round(float(row["avg_wait"]), 6) for row in policy_runs],
                "p95_wait": policy["metrics"]["p95_wait"]["mean"],
                "p99_wait": policy["metrics"]["p99_wait"]["mean"],
                "worst_floor_mean_wait": policy["metrics"]["worst_floor_mean_wait"]["mean"],
                "energy_proxy": policy["metrics"]["energy_proxy"]["mean"],
                "avg_wait_delta_vs_collective": policy["paired_vs_collective"]["avg_wait"]["delta_mean"],
                "avg_wait_delta_ci95_halfwidth": policy["paired_vs_collective"]["avg_wait"]["delta_ci95_halfwidth"],
                "guardrail_classification": policy["guardrail_classification"],
            }
        scenarios[scenario["scenario"]] = {
            "trace_digest_manifest_sha256": _trace_manifest_sha256(scenario["trace_digests"]),
            "policies": policies,
        }
    return {
        "schema": "elevator-queue-lab.m3-regression-baseline.v2",
        "source": {
            "generator": "scripts/run_experiment.py --matrix --seconds 180 --seeds 30",
            "artifact_sha256": artifact_sha256,
            "warmup_seconds": int(window["warmup_seconds"]),
            "measurement_seconds": int(window["measurement_seconds"]),
            "seeds": seed_counts.pop(),
            "demand_contract": matrix.get("demand_contract"),
        },
        "scenarios": scenarios,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the checked M3 regression baseline from a matrix artifact.")
    parser.add_argument("matrix", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/m3-regression-baseline.json"),
    )
    args = parser.parse_args()
    raw = args.matrix.read_bytes()
    matrix = json.loads(raw.decode("utf-8"))
    baseline = build_baseline(matrix, hashlib.sha256(raw).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(baseline, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
