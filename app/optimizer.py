from __future__ import annotations

import random
from dataclasses import dataclass

from .policies import QueueWeights
from .simulator import ElevatorSimulation


@dataclass(frozen=True, slots=True)
class CandidateResult:
    weights: QueueWeights
    score: float
    avg_wait: float
    p95_wait: float
    missed_capacity: float


def _objective(metrics: dict[str, float | int]) -> float:
    return (
        float(metrics["avg_wait"])
        + 0.35 * float(metrics["p95_wait"])
        + 0.7 * float(metrics["missed_capacity"])
    )


def evaluate_weights(
    weights: QueueWeights,
    scenario: str,
    seconds: int = 900,
    seeds: tuple[int, ...] = (3, 7),
) -> CandidateResult:
    summaries: list[dict[str, float | int]] = []
    for seed in seeds:
        simulation = ElevatorSimulation(
            scenario=scenario,
            policy_name="adaptive",
            seed=seed,
            weights=weights,
        )
        summaries.append(simulation.run(seconds))

    count = len(summaries)
    avg_wait = sum(float(item["avg_wait"]) for item in summaries) / count
    p95_wait = sum(float(item["p95_wait"]) for item in summaries) / count
    missed = sum(float(item["missed_capacity"]) for item in summaries) / count
    score = sum(_objective(item) for item in summaries) / count
    return CandidateResult(weights, score, avg_wait, p95_wait, missed)


def optimize_queue_weights(
    scenario: str,
    seconds: int = 900,
    candidates: int = 16,
    seed: int = 101,
) -> tuple[CandidateResult, CandidateResult]:
    """Small deterministic random search; transparent on purpose for the first MVP."""

    randomizer = random.Random(seed)
    baseline = evaluate_weights(QueueWeights(), scenario, seconds)
    best = baseline
    for _ in range(candidates):
        weights = QueueWeights(
            eta=randomizer.uniform(0.65, 1.5),
            load=randomizer.uniform(12.0, 42.0),
            stops=randomizer.uniform(2.0, 9.0),
            direction=randomizer.uniform(6.0, 24.0),
            saturation=randomizer.uniform(45.0, 120.0),
        )
        result = evaluate_weights(weights, scenario, seconds)
        if result.score < best.score:
            best = result
    return baseline, best


def benchmark_policies(
    scenario: str,
    seconds: int = 1200,
    seed: int = 11,
    adaptive_weights: QueueWeights | None = None,
) -> list[dict[str, float | int | str]]:
    results: list[dict[str, float | int | str]] = []
    for policy in ("legacy_sticky", "collective", "queue_aware", "adaptive"):
        simulation = ElevatorSimulation(
            scenario=scenario,
            policy_name=policy,
            seed=seed,
            weights=adaptive_weights if policy == "adaptive" else None,
        )
        metrics = simulation.run(seconds)
        results.append({"policy": policy, **metrics})
    return results

