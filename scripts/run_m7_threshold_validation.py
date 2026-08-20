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

from app.theory import ParametricOfficeDemand
from run_m7_theory_sweep import run_cell


VALIDATION_INTENSITIES = (13.0, 19.0, 25.0)
VALIDATION_UP_PROBABILITIES = (0.10, 0.25, 0.40, 0.60, 0.75, 0.90)


def gated_policy_projection(cells: list[dict[str, object]], threshold: float) -> dict[str, object]:
    """Project a traffic-regime gate using already-evaluated held-out policy outcomes.

    This is an offline policy-selection calculation, not an additional simulator controller run:
    choose CAPR for cells above the frozen discovery threshold and CAPR-static otherwise.  Because
    the threshold is frozen before this grid is evaluated, the projection is useful prospective
    evidence for the control implication without refitting on validation outcomes.
    """

    always_wait_delta = [
        float(cell["capr_vs_static"]["metrics"]["avg_wait"]["delta_mean"])
        for cell in cells
    ]
    always_energy_ratio = [float(cell["capr_vs_static"]["energy_ratio"]) for cell in cells]
    gate_active = [
        float(cell["demand"]["bidirectional_load_rate"]) >= threshold
        for cell in cells
    ]
    gated_wait_delta = [
        delta if active else 0.0
        for delta, active in zip(always_wait_delta, gate_active, strict=True)
    ]
    gated_energy_ratio = [
        ratio if active else 1.0
        for ratio, active in zip(always_energy_ratio, gate_active, strict=True)
    ]
    oracle_wait_delta = [min(0.0, delta) for delta in always_wait_delta]
    mean_always_wait = mean(always_wait_delta)
    mean_gated_wait = mean(gated_wait_delta)
    mean_oracle_wait = mean(oracle_wait_delta)
    mean_always_energy = mean(always_energy_ratio)
    mean_gated_energy = mean(gated_energy_ratio)
    always_overhead = max(0.0, mean_always_energy - 1.0)
    gated_overhead = max(0.0, mean_gated_energy - 1.0)
    wait_retention = (
        abs(mean_gated_wait) / abs(mean_always_wait)
        if mean_always_wait < 0.0 and mean_gated_wait <= 0.0
        else 0.0
    )
    oracle_retention = (
        abs(mean_gated_wait) / abs(mean_oracle_wait)
        if mean_oracle_wait < 0.0 and mean_gated_wait <= 0.0
        else 0.0
    )
    overhead_reduction = (
        1.0 - gated_overhead / always_overhead if always_overhead > 0.0 else 0.0
    )
    return {
        "interpretation": (
            "offline held-out selection: use CAPR when frozen B threshold is active, "
            "otherwise use CAPR-static; no validation refit"
        ),
        "active_cells": sum(gate_active),
        "total_cells": len(cells),
        "mean_avg_wait_delta_vs_static_seconds": round(mean_gated_wait, 6),
        "always_on_capr_mean_avg_wait_delta_vs_static_seconds": round(mean_always_wait, 6),
        "per_cell_mean_oracle_avg_wait_delta_vs_static_seconds": round(mean_oracle_wait, 6),
        "wait_gain_retained_vs_always_on_capr": round(wait_retention, 6),
        "wait_gain_retained_vs_per_cell_mean_oracle": round(oracle_retention, 6),
        "mean_energy_ratio_vs_static": round(mean_gated_energy, 6),
        "always_on_capr_mean_energy_ratio_vs_static": round(mean_always_energy, 6),
        "energy_overhead_reduction_vs_always_on_capr": round(overhead_reduction, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the frozen M7 phase threshold on an unseen grid")
    parser.add_argument(
        "--discovery",
        type=Path,
        default=ROOT / "evidence" / "m7-bidirectional-load-sweep.json",
    )
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evidence" / "m7-threshold-validation.json",
    )
    args = parser.parse_args()
    discovery_path = args.discovery.resolve()
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    frozen = discovery["theory"]["best_single_threshold"]
    threshold = float(frozen["threshold"])
    direction = str(frozen["direction"])

    cells = [
        run_cell(
            ParametricOfficeDemand(intensity, up_probability),
            seconds=args.seconds,
            seeds=args.seeds,
            policies=("capr_static", "capr"),
        )
        for intensity in VALIDATION_INTENSITIES
        for up_probability in VALIDATION_UP_PROBABILITIES
    ]
    confusion = {"true_positive": 0, "false_positive": 0, "true_negative": 0, "false_negative": 0}
    for cell in cells:
        rate = float(cell["demand"]["bidirectional_load_rate"])
        predicted = rate >= threshold if direction == "above" else rate <= threshold
        actual = bool(cell["capr_vs_static"]["supported_wait_gain"])
        cell["frozen_threshold_prediction"] = predicted
        cell["prediction_correct"] = predicted == actual
        if predicted and actual:
            confusion["true_positive"] += 1
        elif predicted and not actual:
            confusion["false_positive"] += 1
        elif not predicted and actual:
            confusion["false_negative"] += 1
        else:
            confusion["true_negative"] += 1

    correct = sum(bool(cell["prediction_correct"]) for cell in cells)
    true_positive = confusion["true_positive"]
    false_positive = confusion["false_positive"]
    false_negative = confusion["false_negative"]
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0

    fit = discovery["theory"]["linear_wait_delta_fit"]
    intercept = float(fit["intercept_seconds"])
    slope = float(fit["slope_seconds_per_bidirectional_pax_per_min"])
    observed = [float(cell["capr_vs_static"]["metrics"]["avg_wait"]["delta_mean"]) for cell in cells]
    predicted = [
        intercept + slope * float(cell["demand"]["bidirectional_load_rate"])
        for cell in cells
    ]
    errors = [actual - estimate for actual, estimate in zip(observed, predicted, strict=True)]
    observed_mean = mean(observed)
    predicted_mean = mean(predicted)
    covariance = sum(
        (actual - observed_mean) * (estimate - predicted_mean)
        for actual, estimate in zip(observed, predicted, strict=True)
    )
    observed_scale = math.sqrt(sum((actual - observed_mean) ** 2 for actual in observed))
    predicted_scale = math.sqrt(sum((estimate - predicted_mean) ** 2 for estimate in predicted))
    correlation = covariance / (observed_scale * predicted_scale) if observed_scale and predicted_scale else 0.0
    payload = {
        "schema": "elevator-queue-lab.m7-threshold-validation.v1",
        "frozen_discovery_threshold": {
            "threshold": threshold,
            "direction": direction,
            "source": (
                str(discovery_path.relative_to(ROOT))
                if discovery_path.is_relative_to(ROOT)
                else str(discovery_path)
            ),
        },
        "method": {
            "seconds": args.seconds,
            "seeds": args.seeds,
            "intensity_grid": list(VALIDATION_INTENSITIES),
            "lobby_up_probability_grid": list(VALIDATION_UP_PROBABILITIES),
            "policies": ["capr_static", "capr"],
            "grid_was_not_used_to_fit_threshold": True,
        },
        "result": {
            "accuracy": round(correct / len(cells), 6),
            "correct_cells": correct,
            "total_cells": len(cells),
            "confusion": confusion,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "all_threshold_positive_cells_have_negative_mean_delta": all(
                float(cell["capr_vs_static"]["metrics"]["avg_wait"]["delta_mean"]) < 0.0
                for cell in cells
                if bool(cell["frozen_threshold_prediction"])
            ),
            "supported_wait_gain_cells": sum(
                bool(cell["capr_vs_static"]["supported_wait_gain"]) for cell in cells
            ),
            "clean_gain_cells": sum(bool(cell["capr_vs_static"]["clean_gain"]) for cell in cells),
            "frozen_linear_effect_model": {
                "correlation_observed_vs_predicted": round(correlation, 6),
                "mae_seconds": round(mean(abs(error) for error in errors), 6),
                "rmse_seconds": round(math.sqrt(mean(error * error for error in errors)), 6),
            },
            "gated_policy_projection": gated_policy_projection(cells, threshold),
        },
        "cells": cells,
    }
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["result"], indent=2))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
