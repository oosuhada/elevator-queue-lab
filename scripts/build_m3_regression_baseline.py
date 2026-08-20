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
        for policy in scenario["policies"]:
            policies[policy["policy"]] = {
                "avg_wait": policy["metrics"]["avg_wait"]["mean"],
                "p95_wait": policy["metrics"]["p95_wait"]["mean"],
                "energy_proxy": policy["metrics"]["energy_proxy"]["mean"],
                "guardrail_classification": policy["guardrail_classification"],
            }
        scenarios[scenario["scenario"]] = {
            "trace_digest_manifest_sha256": _trace_manifest_sha256(scenario["trace_digests"]),
            "policies": policies,
        }
    return {
        "schema": "elevator-queue-lab.m3-regression-baseline.v1",
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
