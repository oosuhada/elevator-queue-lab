from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, pstdev, stdev
from typing import Iterable

from .simulator import ElevatorSimulation


EFFECT_SIZE_CAP = 20.0


def percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be between 0 and 1")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def ci95_halfwidth(values: Iterable[float]) -> float:
    samples = [float(value) for value in values]
    if len(samples) < 2:
        return 0.0
    return 1.96 * stdev(samples) / math.sqrt(len(samples))


def paired_cohens_dz(differences: Iterable[float]) -> float:
    samples = [float(value) for value in differences]
    if len(samples) < 2:
        return 0.0
    center = mean(samples)
    spread = stdev(samples)
    if spread == 0:
        if center == 0:
            return 0.0
        return math.copysign(EFFECT_SIZE_CAP, center)
    return max(-EFFECT_SIZE_CAP, min(EFFECT_SIZE_CAP, center / spread))


def analyze_simulation(simulation: ElevatorSimulation) -> dict[str, float | int | dict[str, float]]:
    arrivals: dict[int, tuple[float, int]] = {}
    wait_by_floor: dict[int, list[float]] = defaultdict(list)
    waits: list[float] = []
    journeys: list[float] = []

    for event in simulation.ledger.events:
        passenger_id = event.passenger_id
        if event.kind == "arrival" and passenger_id is not None and event.floor is not None:
            arrivals[passenger_id] = (event.sim_time, event.floor)
        elif event.kind == "board" and passenger_id is not None:
            arrival = arrivals.get(passenger_id)
            if arrival is not None:
                wait = event.sim_time - arrival[0]
                waits.append(wait)
                wait_by_floor[arrival[1]].append(wait)
        elif event.kind == "alight" and passenger_id is not None:
            arrival = arrivals.get(passenger_id)
            if arrival is not None:
                journeys.append(event.sim_time - arrival[0])

    floor_means = {
        str(floor): mean(values)
        for floor, values in sorted(wait_by_floor.items())
        if values
    }
    floor_values = list(floor_means.values())
    worst_floor_wait = max(floor_values, default=0.0)
    best_floor_wait = min(floor_values, default=0.0)
    floor_wait_std = pstdev(floor_values) if len(floor_values) > 1 else 0.0

    event_counts = simulation.ledger.counts()
    distance_m = sum(
        elevator.distance_travelled * simulation.config.floor_height_m
        for elevator in simulation.elevators
    )
    departures = event_counts.get("car_depart", 0)
    arrivals_count = event_counts.get("car_arrive", 0)
    energy_proxy = distance_m + 8.0 * departures + 2.0 * arrivals_count

    elapsed_minutes = max(simulation.sim_time / 60.0, 1e-9)
    audit = simulation.audit()
    unfinished = int(audit["waiting"]) + int(audit["onboard"])
    metrics = simulation.metrics.snapshot(simulation.sim_time)

    return {
        "arrivals": int(metrics["arrivals"]),
        "served": int(metrics["served"]),
        "unfinished": unfinished,
        "throughput_per_min": int(metrics["served"]) / elapsed_minutes,
        "avg_wait": mean(waits) if waits else 0.0,
        "p50_wait": percentile(waits, 0.50),
        "p95_wait": percentile(waits, 0.95),
        "p99_wait": percentile(waits, 0.99),
        "max_wait": max(waits, default=0.0),
        "avg_journey": mean(journeys) if journeys else 0.0,
        "p95_journey": percentile(journeys, 0.95),
        "p99_journey": percentile(journeys, 0.99),
        "capacity_misses": int(metrics["missed_capacity"]),
        "reassignments": int(metrics.get("reassignments", 0)),
        "invalidations": int(metrics.get("invalidations", 0)),
        "abandoned": int(metrics.get("abandoned", 0)),
        "distance_m": distance_m,
        "car_departures": departures,
        "door_service_arrivals": arrivals_count,
        "energy_proxy": energy_proxy,
        "worst_floor_mean_wait": worst_floor_wait,
        "best_floor_mean_wait": best_floor_wait,
        "floor_wait_gap": worst_floor_wait - best_floor_wait,
        "floor_wait_std": floor_wait_std,
        "floor_mean_waits": {key: round(value, 6) for key, value in floor_means.items()},
    }


def summarize_metric(rows: list[dict[str, object]], metric: str) -> dict[str, float]:
    values = [float(row[metric]) for row in rows]
    return {
        "mean": mean(values) if values else 0.0,
        "ci95_halfwidth": ci95_halfwidth(values),
        "min": min(values, default=0.0),
        "max": max(values, default=0.0),
    }


def paired_comparison(
    candidate_rows: list[dict[str, object]],
    reference_rows: list[dict[str, object]],
    metric: str,
) -> dict[str, float]:
    reference_by_seed = {int(row["seed"]): float(row[metric]) for row in reference_rows}
    differences = [
        float(row[metric]) - reference_by_seed[int(row["seed"])]
        for row in candidate_rows
        if int(row["seed"]) in reference_by_seed
    ]
    return {
        "delta_mean": mean(differences) if differences else 0.0,
        "delta_ci95_halfwidth": ci95_halfwidth(differences),
        "paired_cohens_dz": paired_cohens_dz(differences),
    }


def guardrail_classification(
    candidate: dict[str, float],
    reference: dict[str, float],
) -> str:
    if candidate["avg_wait"] >= reference["avg_wait"]:
        return "no_mean_improvement"
    p95_regression = candidate["p95_wait"] > reference["p95_wait"] * 1.05
    fairness_regression = candidate["worst_floor_mean_wait"] > reference["worst_floor_mean_wait"] + 5.0
    energy_regression = candidate["energy_proxy"] > reference["energy_proxy"] * 1.10
    if p95_regression or fairness_regression or energy_regression:
        return "mean_improves_with_guardrail_tradeoff"
    return "candidate_improvement"
