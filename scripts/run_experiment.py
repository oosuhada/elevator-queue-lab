from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.analytics import (
    analyze_simulation,
    guardrail_classification,
    paired_comparison,
    summarize_metric,
)
from app.domain import SimulationConfig
from app.scenarios import SCENARIOS, SCENARIO_METADATA, generate_scenario_trace
from app.simulator import ElevatorSimulation


POLICIES = (
    "legacy_sticky",
    "nearest_car",
    "collective",
    "queue_aware",
    "capr",
)
REFERENCE_POLICY = "collective"
SUMMARY_METRICS = (
    "avg_wait",
    "p50_wait",
    "p95_wait",
    "p99_wait",
    "max_wait",
    "avg_journey",
    "p95_journey",
    "p99_journey",
    "throughput_per_min",
    "unfinished",
    "capacity_misses",
    "reassignments",
    "invalidations",
    "avg_reassignment_latency",
    "p95_reassignment_latency",
    "abandoned",
    "distance_m",
    "energy_proxy",
    "worst_floor_mean_wait",
    "floor_wait_gap",
    "floor_wait_std",
)
LOWER_IS_BETTER = {
    "avg_wait",
    "p50_wait",
    "p95_wait",
    "p99_wait",
    "max_wait",
    "avg_journey",
    "p95_journey",
    "p99_journey",
    "unfinished",
    "capacity_misses",
    "avg_reassignment_latency",
    "p95_reassignment_latency",
    "abandoned",
    "distance_m",
    "energy_proxy",
    "worst_floor_mean_wait",
    "floor_wait_gap",
    "floor_wait_std",
}


def measurement_window(seconds: int) -> dict[str, int]:
    if seconds <= 0:
        raise ValueError("seconds must be positive")
    # M3 uses synthetic traces from t=0 and intentionally has no warm-up period.
    # Keeping this explicit in every artifact prevents later benchmark runs from
    # silently changing the measurement window.
    return {
        "warmup_seconds": 0,
        "measurement_start_seconds": 0,
        "measurement_seconds": seconds,
        "measurement_end_seconds": seconds,
    }


def run_scenario(
    scenario: str,
    seconds: int,
    seeds: int,
    *,
    control_mode: str = "conventional",
) -> dict[str, object]:
    if seeds <= 0:
        raise ValueError("seeds must be positive")
    window = measurement_window(seconds)
    config = SimulationConfig(control_mode=control_mode)
    traces = {
        seed: generate_scenario_trace(scenario, seconds, seed)
        for seed in range(1, seeds + 1)
    }
    raw_runs: list[dict[str, object]] = []
    for seed, trace in traces.items():
        for policy in POLICIES:
            simulation = ElevatorSimulation(
                scenario=scenario,
                policy_name=policy,
                seed=seed,
                trace=trace,
                config=config,
            )
            simulation.run(seconds)
            audit = simulation.audit()
            if not audit["ok"]:
                raise RuntimeError(
                    f"audit failed scenario={scenario} policy={policy} seed={seed}: {audit}"
                )
            analysis = analyze_simulation(simulation)
            raw_runs.append(
                {
                    "scenario": scenario,
                    "policy": policy,
                    "seed": seed,
                    "trace_digest": trace.digest,
                    "warmup_seconds": window["warmup_seconds"],
                    "measurement_start_seconds": window["measurement_start_seconds"],
                    "measurement_seconds": window["measurement_seconds"],
                    "measurement_end_seconds": window["measurement_end_seconds"],
                    **analysis,
                }
            )

    by_policy = {
        policy: [row for row in raw_runs if row["policy"] == policy]
        for policy in POLICIES
    }
    reference_rows = by_policy[REFERENCE_POLICY]
    summaries: list[dict[str, object]] = []
    reference_means = {
        metric: mean(float(row[metric]) for row in reference_rows)
        for metric in SUMMARY_METRICS
    }

    for policy in POLICIES:
        rows = by_policy[policy]
        metric_summary = {
            metric: {
                key: round(value, 6)
                for key, value in summarize_metric(rows, metric).items()
            }
            for metric in SUMMARY_METRICS
        }
        comparisons = {
            metric: {
                key: round(value, 6)
                for key, value in paired_comparison(rows, reference_rows, metric).items()
            }
            for metric in (
                "avg_wait",
                "p95_wait",
                "p99_wait",
                "worst_floor_mean_wait",
                "energy_proxy",
            )
        }
        candidate_means = {
            metric: float(metric_summary[metric]["mean"])
            for metric in SUMMARY_METRICS
        }
        guardrail = (
            "reference"
            if policy == REFERENCE_POLICY
            else guardrail_classification(candidate_means, reference_means)
        )
        summaries.append(
            {
                "policy": policy,
                "runs": len(rows),
                "metrics": metric_summary,
                "paired_vs_collective": comparisons,
                "guardrail_classification": guardrail,
            }
        )

    return {
        "scenario": scenario,
        "description": SCENARIO_METADATA[scenario].description,
        "segments": list(SCENARIO_METADATA[scenario].segments),
        "seconds": seconds,
        "seeds": seeds,
        "measurement_window": window,
        "trace_digests": {
            str(seed): trace.digest for seed, trace in traces.items()
        },
        "policies": summaries,
        "raw_runs": raw_runs,
    }


def _interpretation() -> dict[str, str]:
    return {
        "effect_size": "paired Cohen's dz on per-seed candidate minus collective outcomes",
        "ci": "normal-approximation 95% confidence interval half-width across seeded runs",
        "energy_proxy": "unitless comparative proxy; not measured kWh",
        "reassignment_latency": (
            "seconds from the start of a hall/destination assignment ownership interval "
            "to a subsequent reassignment of the same call key; zero when no reassignment occurs"
        ),
        "warmup": "M3 synthetic benchmarks explicitly use a zero-second warm-up window",
        "guardrail_rule": (
            "mean-wait improvement is not an unconditional win if P95 wait >5%, "
            "worst-floor mean wait >5s, or energy proxy >10% worse than collective"
        ),
    }


def run_experiment(
    scenario: str,
    seconds: int,
    seeds: int,
    *,
    control_mode: str = "conventional",
) -> dict[str, object]:
    config = SimulationConfig(control_mode=control_mode)
    return {
        "schema": "elevator-queue-lab.experiment.v2",
        "reference_policy": REFERENCE_POLICY,
        "common_random_numbers": True,
        "control_mode": control_mode,
        "measurement_window": measurement_window(seconds),
        "simulation_config": config.as_dict(),
        "scenario_matrix": [
            run_scenario(
                scenario,
                seconds,
                seeds,
                control_mode=control_mode,
            )
        ],
        "interpretation": _interpretation(),
    }


def run_matrix(
    seconds: int,
    seeds: int,
    *,
    control_mode: str = "conventional",
    scenarios: Iterable[str] = SCENARIOS,
) -> dict[str, object]:
    config = SimulationConfig(control_mode=control_mode)
    selected = tuple(scenarios)
    return {
        "schema": "elevator-queue-lab.experiment.v2",
        "reference_policy": REFERENCE_POLICY,
        "common_random_numbers": True,
        "control_mode": control_mode,
        "measurement_window": measurement_window(seconds),
        "simulation_config": config.as_dict(),
        "scenario_matrix": [
            run_scenario(
                scenario,
                seconds,
                seeds,
                control_mode=control_mode,
            )
            for scenario in selected
        ],
        "interpretation": _interpretation(),
    }


def _write_csv_artifacts(payload: dict[str, object], output: Path) -> tuple[Path, Path]:
    runs_path = output.with_name(f"{output.stem}.runs.csv")
    summary_path = output.with_name(f"{output.stem}.summary.csv")
    raw_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for scenario in payload["scenario_matrix"]:
        raw_rows.extend(scenario["raw_runs"])
        for policy in scenario["policies"]:
            row: dict[str, object] = {
                "scenario": scenario["scenario"],
                "policy": policy["policy"],
                "runs": policy["runs"],
                "guardrail_classification": policy["guardrail_classification"],
            }
            for metric, values in policy["metrics"].items():
                row[f"{metric}_mean"] = values["mean"]
                row[f"{metric}_ci95_halfwidth"] = values["ci95_halfwidth"]
            for metric, values in policy["paired_vs_collective"].items():
                row[f"{metric}_delta_vs_collective"] = values["delta_mean"]
                row[f"{metric}_dz_vs_collective"] = values["paired_cohens_dz"]
            summary_rows.append(row)

    output.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(runs_path, raw_rows)
    _write_csv(summary_path, summary_rows)
    return runs_path, summary_path


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for source in rows:
            row = dict(source)
            if isinstance(row.get("floor_mean_waits"), dict):
                row["floor_mean_waits"] = json.dumps(
                    row["floor_mean_waits"],
                    sort_keys=True,
                    separators=(",", ":"),
                )
            writer.writerow(row)


def _compact_console_summary(payload: dict[str, object]) -> dict[str, object]:
    scenarios: list[dict[str, object]] = []
    for scenario in payload["scenario_matrix"]:
        policies = []
        for policy in scenario["policies"]:
            policies.append(
                {
                    "policy": policy["policy"],
                    "avg_wait": policy["metrics"]["avg_wait"]["mean"],
                    "p95_wait": policy["metrics"]["p95_wait"]["mean"],
                    "energy_proxy": policy["metrics"]["energy_proxy"]["mean"],
                    "guardrail": policy["guardrail_classification"],
                }
            )
        scenarios.append({"scenario": scenario["scenario"], "policies": policies})
    return {
        "schema": payload["schema"],
        "reference_policy": payload["reference_policy"],
        "measurement_window": payload["measurement_window"],
        "scenarios": scenarios,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="morning", choices=SCENARIOS)
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="run morning/lunch/normal/evening/shock/mixed_day",
    )
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument(
        "--control-mode",
        choices=("conventional", "destination"),
        default="conventional",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = (
        run_matrix(args.seconds, args.seeds, control_mode=args.control_mode)
        if args.matrix
        else run_experiment(
            args.scenario,
            args.seconds,
            args.seeds,
            control_mode=args.control_mode,
        )
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        runs_path, summary_path = _write_csv_artifacts(payload, args.output)
        print(
            json.dumps(
                {
                    "json": str(args.output),
                    "runs_csv": str(runs_path),
                    "summary_csv": str(summary_path),
                    **_compact_console_summary(payload),
                },
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
        )
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
