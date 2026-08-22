from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.analytics import analyze_simulation, paired_comparison, summarize_metric
from app.domain import SimulationConfig
from app.simulator import ElevatorSimulation
from app.theory import ParametricOfficeDemand, generate_parametric_trace


POLICIES = ("capr_static", "capr", "collective")
DEFAULT_INTENSITIES = (5.0, 10.0, 16.0, 22.0, 28.0)
DEFAULT_UP_PROBABILITIES = (0.03, 0.15, 0.30, 0.45, 0.50, 0.70, 0.85, 0.97)
METRICS = (
    "avg_wait",
    "p95_wait",
    "p99_wait",
    "energy_proxy",
    "worst_floor_mean_wait",
    "reassignments",
    "capacity_misses",
)


def run_cell(
    spec: ParametricOfficeDemand,
    *,
    seconds: int,
    seeds: int,
    policies: tuple[str, ...] = POLICIES,
) -> dict[str, object]:
    config = SimulationConfig()
    traces = {
        seed: generate_parametric_trace(spec, seconds, seed)
        for seed in range(1, seeds + 1)
    }
    rows: list[dict[str, object]] = []
    for seed, trace in traces.items():
        for policy in policies:
            simulation = ElevatorSimulation(
                scenario="normal",
                policy_name=policy,
                seed=seed,
                trace=trace,
                config=config,
            )
            simulation.run(seconds)
            audit = simulation.audit()
            if not audit["ok"]:
                raise RuntimeError(
                    f"M7 audit failed policy={policy} seed={seed} spec={spec}: {audit}"
                )
            analysis = analyze_simulation(simulation)
            rows.append(
                {
                    "seed": seed,
                    "policy": policy,
                    **{metric: analysis[metric] for metric in METRICS},
                }
            )

    by_policy = {
        policy: [row for row in rows if row["policy"] == policy]
        for policy in policies
    }
    policy_summary: dict[str, object] = {}
    for policy, policy_rows in by_policy.items():
        policy_summary[policy] = {
            metric: {
                key: round(value, 6)
                for key, value in summarize_metric(policy_rows, metric).items()
            }
            for metric in METRICS
        }

    static_rows = by_policy["capr_static"]
    capr_rows = by_policy["capr"]
    comparison = {
        metric: {
            key: round(value, 6)
            for key, value in paired_comparison(capr_rows, static_rows, metric).items()
        }
        for metric in METRICS
    }
    wait_cmp = comparison["avg_wait"]
    p95_cmp = comparison["p95_wait"]
    energy_cmp = comparison["energy_proxy"]
    static_energy = float(policy_summary["capr_static"]["energy_proxy"]["mean"])
    capr_energy = float(policy_summary["capr"]["energy_proxy"]["mean"])
    energy_ratio = capr_energy / static_energy if static_energy else 1.0
    supported_wait_gain = (
        float(wait_cmp["delta_mean"]) + float(wait_cmp["delta_ci95_halfwidth"]) < 0.0
    )
    supported_wait_loss = (
        float(wait_cmp["delta_mean"]) - float(wait_cmp["delta_ci95_halfwidth"]) > 0.0
    )
    clean_gain = (
        supported_wait_gain
        and float(p95_cmp["delta_mean"]) <= 0.0
        and energy_ratio <= 1.10
    )
    per_seed_wait_delta = [
        round(float(capr["avg_wait"]) - float(static["avg_wait"]), 6)
        for capr, static in zip(capr_rows, static_rows, strict=True)
    ]

    return {
        "demand": spec.as_dict(),
        "trace_digests": {str(seed): trace.digest for seed, trace in traces.items()},
        "policies": policy_summary,
        "capr_vs_static": {
            "metrics": comparison,
            "energy_ratio": round(energy_ratio, 6),
            "supported_wait_gain": supported_wait_gain,
            "supported_wait_loss": supported_wait_loss,
            "clean_gain": clean_gain,
            "per_seed_avg_wait_delta": per_seed_wait_delta,
        },
    }


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    x_bar = mean(xs)
    y_bar = mean(ys)
    numerator = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys, strict=True))
    x_scale = math.sqrt(sum((x - x_bar) ** 2 for x in xs))
    y_scale = math.sqrt(sum((y - y_bar) ** 2 for y in ys))
    if x_scale == 0.0 or y_scale == 0.0:
        return 0.0
    return numerator / (x_scale * y_scale)


def _best_threshold(cells: list[dict[str, object]]) -> dict[str, object]:
    points = sorted(
        {
            float(cell["demand"]["bidirectional_load_rate"])
            for cell in cells
        }
    )
    thresholds = [0.0]
    thresholds.extend((left + right) / 2.0 for left, right in zip(points, points[1:]))
    thresholds.append(points[-1] + 1e-6)
    best: dict[str, object] | None = None
    for direction in ("above", "below"):
        for threshold in thresholds:
            correct = 0
            for cell in cells:
                rate = float(cell["demand"]["bidirectional_load_rate"])
                predicted = rate >= threshold if direction == "above" else rate <= threshold
                actual = bool(cell["capr_vs_static"]["supported_wait_gain"])
                correct += int(predicted == actual)
            accuracy = correct / len(cells)
            candidate = {
                "threshold": round(threshold, 6),
                "direction": direction,
                "accuracy": round(accuracy, 6),
                "correct_cells": correct,
                "total_cells": len(cells),
            }
            if best is None or accuracy > float(best["accuracy"]):
                best = candidate
    assert best is not None
    return best


def extract_theory(cells: list[dict[str, object]]) -> dict[str, object]:
    rates = [float(cell["demand"]["bidirectional_load_rate"]) for cell in cells]
    deltas = [float(cell["capr_vs_static"]["metrics"]["avg_wait"]["delta_mean"]) for cell in cells]
    p95_deltas = [float(cell["capr_vs_static"]["metrics"]["p95_wait"]["delta_mean"]) for cell in cells]
    energy_ratios = [float(cell["capr_vs_static"]["energy_ratio"]) for cell in cells]
    reassignments = [float(cell["policies"]["capr"]["reassignments"]["mean"]) for cell in cells]
    gain_cells = [cell for cell in cells if cell["capr_vs_static"]["supported_wait_gain"]]
    clean_cells = [cell for cell in cells if cell["capr_vs_static"]["clean_gain"]]
    losses = [cell for cell in cells if cell["capr_vs_static"]["supported_wait_loss"]]

    down_cells = [cell for cell in cells if float(cell["demand"]["lobby_up_probability"]) < 0.5]
    up_cells = [cell for cell in cells if float(cell["demand"]["lobby_up_probability"]) > 0.5]

    def mean_delta(subset: list[dict[str, object]]) -> float:
        if not subset:
            return 0.0
        return mean(
            float(cell["capr_vs_static"]["metrics"]["avg_wait"]["delta_mean"])
            for cell in subset
        )

    threshold = _best_threshold(cells)
    linear_fit = _linear_fit(rates, deltas)
    return {
        "candidate_law": (
            "continuous predictive reassignment value is conditioned by both demand intensity "
            "and directional mixing; bidirectional load rate is tested as a one-number collapse"
        ),
        "bidirectional_load_rate_definition": "lambda * 4*p_up*(1-p_up) passengers/minute",
        "pearson_bidirectional_load_rate_vs_capr_wait_delta": round(_pearson(rates, deltas), 6),
        "pearson_bidirectional_load_rate_vs_p95_wait_delta": round(_pearson(rates, p95_deltas), 6),
        "pearson_bidirectional_load_rate_vs_energy_ratio": round(_pearson(rates, energy_ratios), 6),
        "pearson_bidirectional_load_rate_vs_reassignments": round(_pearson(rates, reassignments), 6),
        "linear_wait_delta_fit": linear_fit,
        "best_single_threshold": {
            **threshold,
            "confusion": _threshold_confusion(cells, threshold),
        },
        "leave_one_intensity_out": _leave_one_intensity_out(cells),
        "phase_bins": _phase_bins(cells),
        "uppeak_counterflow_boundary": _counterflow_boundary(float(threshold["threshold"])),
        "supported_wait_gain_cells": len(gain_cells),
        "clean_gain_cells": len(clean_cells),
        "supported_wait_loss_cells": len(losses),
        "cell_count": len(cells),
        "mean_wait_delta_seconds": {
            "down_or_balanced": round(mean_delta(down_cells), 6),
            "up_dominant": round(mean_delta(up_cells), 6),
        },
        "strongest_gain_cell": _extreme_cell(cells, minimum=True),
        "strongest_loss_cell": _extreme_cell(cells, minimum=False),
    }


def _linear_fit(xs: list[float], ys: list[float]) -> dict[str, float]:
    x_bar = mean(xs)
    y_bar = mean(ys)
    variance = sum((x - x_bar) ** 2 for x in xs)
    slope = (
        sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, ys, strict=True)) / variance
        if variance
        else 0.0
    )
    intercept = y_bar - slope * x_bar
    predictions = [intercept + slope * x for x in xs]
    total = sum((y - y_bar) ** 2 for y in ys)
    residual = sum((y - prediction) ** 2 for y, prediction in zip(ys, predictions, strict=True))
    r_squared = 1.0 - residual / total if total else 0.0
    zero_crossing = -intercept / slope if slope else 0.0
    return {
        "intercept_seconds": round(intercept, 6),
        "slope_seconds_per_bidirectional_pax_per_min": round(slope, 6),
        "r_squared": round(r_squared, 6),
        "mean_crossover_rate": round(zero_crossing, 6),
    }


def _threshold_confusion(
    cells: list[dict[str, object]],
    threshold: dict[str, object],
) -> dict[str, int]:
    result = {"true_positive": 0, "false_positive": 0, "true_negative": 0, "false_negative": 0}
    cutoff = float(threshold["threshold"])
    direction = str(threshold["direction"])
    for cell in cells:
        rate = float(cell["demand"]["bidirectional_load_rate"])
        predicted = rate >= cutoff if direction == "above" else rate <= cutoff
        actual = bool(cell["capr_vs_static"]["supported_wait_gain"])
        if predicted and actual:
            result["true_positive"] += 1
        elif predicted and not actual:
            result["false_positive"] += 1
        elif not predicted and actual:
            result["false_negative"] += 1
        else:
            result["true_negative"] += 1
    return result


def _leave_one_intensity_out(cells: list[dict[str, object]]) -> dict[str, object]:
    intensities = sorted({float(cell["demand"]["arrivals_per_minute"]) for cell in cells})
    folds: list[dict[str, object]] = []
    for held_out in intensities:
        train = [cell for cell in cells if float(cell["demand"]["arrivals_per_minute"]) != held_out]
        test = [cell for cell in cells if float(cell["demand"]["arrivals_per_minute"]) == held_out]
        threshold = _best_threshold(train)
        cutoff = float(threshold["threshold"])
        direction = str(threshold["direction"])
        correct = 0
        for cell in test:
            rate = float(cell["demand"]["bidirectional_load_rate"])
            predicted = rate >= cutoff if direction == "above" else rate <= cutoff
            correct += int(predicted == bool(cell["capr_vs_static"]["supported_wait_gain"]))
        folds.append(
            {
                "held_out_arrivals_per_minute": held_out,
                "trained_threshold": round(cutoff, 6),
                "direction": direction,
                "accuracy": round(correct / len(test), 6),
                "correct_cells": correct,
                "total_cells": len(test),
            }
        )
    return {
        "mean_accuracy": round(mean(float(fold["accuracy"]) for fold in folds), 6),
        "folds": folds,
    }


def _phase_bins(cells: list[dict[str, object]]) -> list[dict[str, object]]:
    bounds = ((0.0, 4.0), (4.0, 8.0), (8.0, 12.0), (12.0, 16.0), (16.0, math.inf))
    result: list[dict[str, object]] = []
    for lower, upper in bounds:
        members = [
            cell
            for cell in cells
            if lower <= float(cell["demand"]["bidirectional_load_rate"]) < upper
        ]
        if not members:
            continue
        result.append(
            {
                "lower": lower,
                "upper": None if math.isinf(upper) else upper,
                "cells": len(members),
                "mean_avg_wait_delta_seconds": round(
                    mean(float(cell["capr_vs_static"]["metrics"]["avg_wait"]["delta_mean"]) for cell in members),
                    6,
                ),
                "mean_energy_ratio": round(
                    mean(float(cell["capr_vs_static"]["energy_ratio"]) for cell in members),
                    6,
                ),
                "supported_wait_gain_cells": sum(
                    bool(cell["capr_vs_static"]["supported_wait_gain"]) for cell in members
                ),
                "clean_gain_cells": sum(bool(cell["capr_vs_static"]["clean_gain"]) for cell in members),
            }
        )
    return result


def _counterflow_boundary(threshold: float) -> list[dict[str, float]]:
    points: list[dict[str, float]] = []
    for intensity in DEFAULT_INTENSITIES:
        if intensity < threshold:
            continue
        ratio = min(1.0, threshold / intensity)
        opposite_share = (1.0 - math.sqrt(max(0.0, 1.0 - ratio))) / 2.0
        points.append(
            {
                "arrivals_per_minute": intensity,
                "critical_opposite_lobby_share": round(opposite_share, 6),
                "small_counterflow_approximation": round(threshold / (4.0 * intensity), 6),
            }
        )
    return points


def _extreme_cell(cells: list[dict[str, object]], *, minimum: bool) -> dict[str, object]:
    chosen = (min if minimum else max)(
        cells,
        key=lambda cell: float(cell["capr_vs_static"]["metrics"]["avg_wait"]["delta_mean"]),
    )
    return {
        "arrivals_per_minute": chosen["demand"]["arrivals_per_minute"],
        "lobby_up_probability": chosen["demand"]["lobby_up_probability"],
        "directional_mixing_index": chosen["demand"]["directional_mixing_index"],
        "bidirectional_load_rate": chosen["demand"]["bidirectional_load_rate"],
        "avg_wait_delta_seconds": chosen["capr_vs_static"]["metrics"]["avg_wait"]["delta_mean"],
        "p95_wait_delta_seconds": chosen["capr_vs_static"]["metrics"]["p95_wait"]["delta_mean"],
        "energy_ratio": chosen["capr_vs_static"]["energy_ratio"],
    }


def run_sweep(
    *,
    seconds: int,
    seeds: int,
    intensities: tuple[float, ...] = DEFAULT_INTENSITIES,
    up_probabilities: tuple[float, ...] = DEFAULT_UP_PROBABILITIES,
) -> dict[str, object]:
    cells = [
        run_cell(
            ParametricOfficeDemand(
                arrivals_per_minute=intensity,
                lobby_up_probability=up_probability,
            ),
            seconds=seconds,
            seeds=seeds,
        )
        for intensity in intensities
        for up_probability in up_probabilities
    ]
    return {
        "schema": "elevator-queue-lab.m7-bidirectional-load-theory.v1",
        "hypothesis": {
            "name": "Bidirectional Load Rate hypothesis",
            "statement": (
                "The marginal value of continuous predictive reassignment is governed by the "
                "amount of simultaneous opposite-direction demand, not arrival intensity alone."
            ),
            "status": "falsifiable project hypothesis; not a claim of established or novel theory",
        },
        "method": {
            "seconds": seconds,
            "seeds": seeds,
            "policies": list(POLICIES),
            "ablation": "capr_static and capr share CAPR scoring and parking; only continuous reassignment differs",
            "simulation_scenario_context": "normal",
            "intensity_grid": list(intensities),
            "lobby_up_probability_grid": list(up_probabilities),
            "trip_purpose_mix": {"lobby": 0.85, "rooftop": 0.10, "interfloor": 0.05},
            "common_random_numbers": True,
        },
        "theory": extract_theory(cells),
        "cells": cells,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M7 controlled traffic phase sweep")
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evidence" / "m7-bidirectional-load-sweep.json",
    )
    args = parser.parse_args()
    payload = run_sweep(seconds=args.seconds, seeds=args.seeds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["theory"], indent=2, ensure_ascii=False))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
