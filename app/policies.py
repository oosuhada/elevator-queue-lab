from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Protocol

from .dispatch import CandidateEvaluation, DispatchDecision, build_evaluation, choose_decision
from .domain import Elevator, HallCall, SimulationConfig


class DispatchPolicy(Protocol):
    name: str
    immediate_reassignment: bool
    continuous_reassignment: bool

    def decide(
        self,
        call: HallCall,
        elevators: Iterable[Elevator],
        config: SimulationConfig,
        *,
        queue_size: int,
        now: float,
    ) -> DispatchDecision: ...

    def parking_floor(self, elevator: Elevator, scenario: str) -> int | None: ...


def _resolve_choice(
    decision: DispatchDecision,
    elevators: Iterable[Elevator],
) -> Elevator | None:
    if decision.chosen_elevator_id is None:
        return None
    return next(
        (item for item in elevators if item.elevator_id == decision.chosen_elevator_id),
        None,
    )


def _legacy_eta_seconds(elevator: Elevator, floor: int) -> float:
    direct = abs(elevator.floor - floor) * 2.0
    queued = len(elevator.stops) * 4.0
    if elevator.stops:
        queued += abs(elevator.stops[0] - elevator.floor) * 1.2
    phase_delay = elevator.phase_timer if elevator.phase != "idle" else 0.0
    if elevator.phase == "moving":
        phase_delay += max(0.0, elevator.travel_duration - elevator.travel_elapsed)
    return direct + queued + phase_delay


@dataclass(slots=True)
class LegacyStickyPolicy:
    """Deliberately sticky comparator resembling stale hall-call assignment behaviour."""

    name: str = "legacy_sticky"
    immediate_reassignment: bool = False
    continuous_reassignment: bool = False

    def decide(
        self,
        call: HallCall,
        elevators: Iterable[Elevator],
        config: SimulationConfig,
        *,
        queue_size: int,
        now: float,
    ) -> DispatchDecision:
        cars = list(elevators)
        if not cars:
            return DispatchDecision(None, (), "no compatible elevator")
        evaluations: list[CandidateEvaluation] = []
        for car in cars:
            base = build_evaluation(
                car,
                call,
                config,
                queue_size=queue_size,
                now=now,
                mode="collective",
            )
            moving_bonus = -8.0 if car.direction != 0 else 0.0
            parked_penalty = 10.0 if car.direction == 0 and car.floor > 10 else 0.0
            score = _legacy_eta_seconds(car, call.floor) + moving_bonus + parked_penalty + car.load_ratio * 8.0
            evaluations.append(
                replace(
                    base,
                    score=score,
                    reason=(
                        f"legacy ETA {_legacy_eta_seconds(car, call.floor):.1f}s; "
                        f"moving bonus {moving_bonus:.1f}; parked penalty {parked_penalty:.1f}"
                    ),
                )
            )
        chosen = min(evaluations, key=lambda item: (item.score, item.elevator_id))
        return DispatchDecision(
            chosen.elevator_id,
            tuple(evaluations),
            f"{chosen.elevator_id} selected by sticky baseline: {chosen.reason}",
        )

    def choose(self, call: HallCall, elevators: Iterable[Elevator]) -> Elevator | None:
        cars = list(elevators)
        return _resolve_choice(
            self.decide(call, cars, SimulationConfig(), queue_size=1, now=call.created_at),
            cars,
        )

    def parking_floor(self, elevator: Elevator, scenario: str) -> int | None:
        return None


@dataclass(slots=True)
class NearestCarPolicy:
    name: str = "nearest_car"
    immediate_reassignment: bool = True
    continuous_reassignment: bool = False

    def decide(
        self,
        call: HallCall,
        elevators: Iterable[Elevator],
        config: SimulationConfig,
        *,
        queue_size: int,
        now: float,
    ) -> DispatchDecision:
        return choose_decision(
            call,
            elevators,
            config,
            queue_size=queue_size,
            now=now,
            mode="nearest",
        )

    def parking_floor(self, elevator: Elevator, scenario: str) -> int | None:
        return None


@dataclass(slots=True)
class CollectivePolicy:
    name: str = "collective"
    immediate_reassignment: bool = True
    continuous_reassignment: bool = False

    def decide(
        self,
        call: HallCall,
        elevators: Iterable[Elevator],
        config: SimulationConfig,
        *,
        queue_size: int,
        now: float,
    ) -> DispatchDecision:
        return choose_decision(
            call,
            elevators,
            config,
            queue_size=queue_size,
            now=now,
            mode="collective",
        )

    def parking_floor(self, elevator: Elevator, scenario: str) -> int | None:
        return 1 if scenario in {"morning", "lunch"} else None


@dataclass(frozen=True, slots=True)
class QueueWeights:
    eta: float = 1.0
    load: float = 22.0
    stops: float = 4.5
    direction: float = 12.0
    saturation: float = 70.0

    def as_dict(self) -> dict[str, float]:
        return {
            "eta": round(self.eta, 3),
            "load": round(self.load, 3),
            "stops": round(self.stops, 3),
            "direction": round(self.direction, 3),
            "saturation": round(self.saturation, 3),
        }


@dataclass(slots=True)
class QueueAwarePolicy:
    weights: QueueWeights = QueueWeights()
    name: str = "queue_aware"
    immediate_reassignment: bool = True
    continuous_reassignment: bool = False

    def with_weights(self, weights: QueueWeights) -> "QueueAwarePolicy":
        return replace(self, weights=weights)

    def decide(
        self,
        call: HallCall,
        elevators: Iterable[Elevator],
        config: SimulationConfig,
        *,
        queue_size: int,
        now: float,
    ) -> DispatchDecision:
        cars = list(elevators)
        evaluations: list[CandidateEvaluation] = []
        for car in cars:
            base = build_evaluation(
                car,
                call,
                config,
                queue_size=queue_size,
                now=now,
                mode="queue_aware",
            )
            mismatch = 1.0 if car.direction and car.direction != call.direction else 0.0
            saturated = 1.0 if base.residual_capacity <= config.capacity_reserve else 0.0
            score = (
                self.weights.eta * base.pickup_eta
                + self.weights.load * car.load_ratio
                + self.weights.stops * len(car.stops)
                + self.weights.direction * mismatch
                + self.weights.saturation * saturated
            )
            evaluations.append(replace(base, score=score))
        if not evaluations:
            return DispatchDecision(None, (), "no compatible elevator")
        chosen = min(evaluations, key=lambda item: (item.score, item.pickup_eta, item.elevator_id))
        return DispatchDecision(
            chosen.elevator_id,
            tuple(evaluations),
            f"{chosen.elevator_id} selected by queue-aware heuristic: {chosen.reason}",
        )

    def choose(self, call: HallCall, elevators: Iterable[Elevator]) -> Elevator | None:
        cars = list(elevators)
        return _resolve_choice(
            self.decide(call, cars, SimulationConfig(), queue_size=1, now=call.created_at),
            cars,
        )

    def parking_floor(self, elevator: Elevator, scenario: str) -> int | None:
        if scenario in {"morning", "lunch"}:
            return 1
        if scenario == "evening":
            return 8 if elevator.bank == "low" else 16
        return 5 if elevator.bank == "low" else 14


@dataclass(slots=True)
class CAPRPolicy:
    """Capacity-Aware Predictive Reassignment controller.

    CAPR continuously re-evaluates the assigned car. Cars predicted to have no usable
    residual capacity at the pickup are made infeasible before they physically pass the call.
    A minimum score gain and assignment cooldown are enforced by the simulator to avoid
    reassignment thrashing.
    """

    name: str = "capr"
    immediate_reassignment: bool = True
    continuous_reassignment: bool = True

    def decide(
        self,
        call: HallCall,
        elevators: Iterable[Elevator],
        config: SimulationConfig,
        *,
        queue_size: int,
        now: float,
    ) -> DispatchDecision:
        return choose_decision(
            call,
            elevators,
            config,
            queue_size=queue_size,
            now=now,
            mode="capr",
        )

    def parking_floor(self, elevator: Elevator, scenario: str) -> int | None:
        # Demand-aware pre-positioning is deliberately simple and explainable at M2.
        if scenario == "morning":
            return 1
        if scenario == "lunch":
            return 1 if elevator.elevator_id.endswith("1") else (6 if elevator.bank == "low" else 14)
        if scenario == "evening":
            return 8 if elevator.bank == "low" else 16
        return 5 if elevator.bank == "low" else 14


def build_policy(name: str, weights: QueueWeights | None = None) -> DispatchPolicy:
    if name == "legacy_sticky":
        return LegacyStickyPolicy()
    if name == "nearest_car":
        return NearestCarPolicy()
    if name == "collective":
        return CollectivePolicy()
    if name in {"queue_aware", "adaptive"}:
        return QueueAwarePolicy(weights=weights or QueueWeights(), name=name)
    if name == "capr":
        return CAPRPolicy()
    raise ValueError(f"Unknown policy: {name}")
