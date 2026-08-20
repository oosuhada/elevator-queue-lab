from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _trace_manifest_sha256(trace_digests: dict[str, str]) -> str:
    manifest = "\n".join(
        f"{seed}:{digest}"
        for seed, digest in sorted(trace_digests.items(), key=lambda item: int(item[0]))
    )
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()


def check_baseline(generated: dict[str, object], baseline: dict[str, object], tolerance: float) -> list[str]:
    failures: list[str] = []
    source = baseline["source"]
    expected_demand_contract = source.get("demand_contract")
    if expected_demand_contract is not None and generated.get("demand_contract") != expected_demand_contract:
        failures.append("demand contract changed")
    window = generated.get("measurement_window", {})
    if int(window.get("warmup_seconds", -1)) != int(source["warmup_seconds"]):
        failures.append("warmup_seconds changed")
    if int(window.get("measurement_seconds", -1)) != int(source["measurement_seconds"]):
        failures.append("measurement_seconds changed")

    generated_scenarios = {
        str(item["scenario"]): item for item in generated["scenario_matrix"]
    }
    for scenario_name, expected in baseline["scenarios"].items():
        actual = generated_scenarios.get(scenario_name)
        if actual is None:
            failures.append(f"missing scenario: {scenario_name}")
            continue
        manifest = _trace_manifest_sha256(actual["trace_digests"])
        if manifest != expected["trace_digest_manifest_sha256"]:
            failures.append(f"trace digest manifest changed: {scenario_name}")
        actual_policies = {item["policy"]: item for item in actual["policies"]}
        for policy_name, expected_policy in expected["policies"].items():
            policy = actual_policies.get(policy_name)
            if policy is None:
                failures.append(f"missing policy: {scenario_name}/{policy_name}")
                continue
            for metric in ("avg_wait", "p95_wait", "p99_wait", "worst_floor_mean_wait", "energy_proxy"):
                observed = float(policy["metrics"][metric]["mean"])
                target = float(expected_policy[metric])
                if abs(observed - target) > tolerance:
                    failures.append(
                        f"{scenario_name}/{policy_name}/{metric}: {observed} != {target}"
                    )
            avg_wait_summary = policy["metrics"]["avg_wait"]
            for key, expected_key in (
                ("ci95_halfwidth", "avg_wait_ci95_halfwidth"),
                ("min", "avg_wait_min"),
                ("max", "avg_wait_max"),
            ):
                observed = float(avg_wait_summary[key])
                target = float(expected_policy[expected_key])
                if abs(observed - target) > tolerance:
                    failures.append(
                        f"{scenario_name}/{policy_name}/avg_wait_{key}: {observed} != {target}"
                    )
            raw_policy_rows = sorted(
                (row for row in actual["raw_runs"] if row["policy"] == policy_name),
                key=lambda row: int(row["seed"]),
            )
            observed_seed_values = [float(row["avg_wait"]) for row in raw_policy_rows]
            expected_seed_values = [float(value) for value in expected_policy["avg_wait_seed_values"]]
            if len(observed_seed_values) != len(expected_seed_values):
                failures.append(
                    f"{scenario_name}/{policy_name}/avg_wait_seed_values length changed: "
                    f"{len(observed_seed_values)} != {len(expected_seed_values)}"
                )
            else:
                for index, (observed, target) in enumerate(zip(observed_seed_values, expected_seed_values), start=1):
                    if abs(observed - target) > tolerance:
                        failures.append(
                            f"{scenario_name}/{policy_name}/avg_wait_seed_values[{index}]: "
                            f"{observed} != {target}"
                        )
                        break
            paired_avg_wait = policy["paired_vs_collective"]["avg_wait"]
            for key, expected_key in (
                ("delta_mean", "avg_wait_delta_vs_collective"),
                ("delta_ci95_halfwidth", "avg_wait_delta_ci95_halfwidth"),
            ):
                observed = float(paired_avg_wait[key])
                target = float(expected_policy[expected_key])
                if abs(observed - target) > tolerance:
                    failures.append(
                        f"{scenario_name}/{policy_name}/{key}: {observed} != {target}"
                    )
            observed_guardrail = policy["guardrail_classification"]
            if observed_guardrail != expected_policy["guardrail_classification"]:
                failures.append(
                    f"{scenario_name}/{policy_name}/guardrail: "
                    f"{observed_guardrail} != {expected_policy['guardrail_classification']}"
                )
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("generated", type=Path)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("evidence/m3-regression-baseline.json"),
    )
    parser.add_argument("--tolerance", type=float, default=1e-6)
    args = parser.parse_args()
    generated = json.loads(args.generated.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    failures = check_baseline(generated, baseline, args.tolerance)
    if failures:
        raise SystemExit("M3 regression baseline failed:\n- " + "\n- ".join(failures))
    print(
        f"M3 regression baseline passed: {len(baseline['scenarios'])} scenarios, "
        f"tolerance={args.tolerance:g}"
    )


if __name__ == "__main__":
    main()
