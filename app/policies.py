from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Protocol

from .domain import Elevator, HallCall


class DispatchPolicy(Protocol):
    name: str
    immediate_reassignment: bool

    def choose(self, call: HallCall, elevators: Iterable[Elevator]) -> Elevator | None: ...

    def parking_floor(self, elevator: Elevator, scenario: str) -> int | None: ...


def _candidate_elevators(call: HallCall, elevators: Iterable[Elevator]) -> list[Elevator]:
    # The destination is unknown at hall-call time in a conventional control system.
    # Bank ownership therefore comes from the pickup floor except at the shared lobby.
    candidates = [elevator for elevator in elevators if elevator.can_serve_floor(call.floor)]
    return candidates


def _eta_seconds(elevator: Elevator, floor: int) -> float:
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
    """A deliberately sticky baseline inspired by frustrating group-control behaviour."""

    name: str = "legacy_sticky"
    immediate_reassignment: bool = False

    def choose(self, call: HallCall, elevators: Iterable[Elevator]) -> Elevator | None:
        candidates = _candidate_elevators(call, elevators)
        if call.floor == 1:
            # At the shared lobby we can infer the bank only after passengers arrive.
            # Keep all cars eligible; the simulator later guards destination service.
            candidates = list(elevators)
        if not candidates:
            return None

        def score(elevator: Elevator) -> float:
            eta = _eta_seconds(elevator, call.floor)
            # Sticky control gives moving cars a scheduling preference and allows idle
            # high-floor cars to remain parked. This is the behaviour we want to compare.
            moving_bonus = -8.0 if elevator.direction != 0 else 0.0
            parked_penalty = 10.0 if elevator.direction == 0 and elevator.floor > 10 else 0.0
            load_penalty = elevator.load_ratio * 8.0
            return eta + moving_bonus + parked_penalty + load_penalty

        return min(candidates, key=score)

    def parking_floor(self, elevator: Elevator, scenario: str) -> int | None:
        # Legacy behaviour does not actively reposition idle cars.
        return None


@dataclass(slots=True)
class CollectivePolicy:
    name: str = "collective"
    immediate_reassignment: bool = True

    def choose(self, call: HallCall, elevators: Iterable[Elevator]) -> Elevator | None:
        candidates = _candidate_elevators(call, elevators)
        if call.floor == 1:
            candidates = list(elevators)
        if not candidates:
            return None

        def score(elevator: Elevator) -> float:
            mismatch = 0.0
            if elevator.direction and elevator.direction != call.direction:
                mismatch = 9.0
            saturation = 45.0 if elevator.load_ratio >= 0.93 else 0.0
            return _eta_seconds(elevator, call.floor) + mismatch + elevator.load_ratio * 14.0 + saturation

        return min(candidates, key=score)

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

    def with_weights(self, weights: QueueWeights) -> "QueueAwarePolicy":
        return replace(self, weights=weights)

    def choose(self, call: HallCall, elevators: Iterable[Elevator]) -> Elevator | None:
        candidates = _candidate_elevators(call, elevators)
        if call.floor == 1:
            candidates = list(elevators)
        if not candidates:
            return None
        weights = self.weights

        def score(elevator: Elevator) -> float:
            mismatch = 1.0 if elevator.direction and elevator.direction != call.direction else 0.0
            saturated = 1.0 if elevator.load_ratio >= 0.86 else 0.0
            return (
                weights.eta * _eta_seconds(elevator, call.floor)
                + weights.load * elevator.load_ratio
                + weights.stops * len(elevator.stops)
                + weights.direction * mismatch
                + weights.saturation * saturated
            )

        return min(candidates, key=score)

    def parking_floor(self, elevator: Elevator, scenario: str) -> int | None:
        if scenario == "morning":
            return 1
        if scenario == "lunch":
            return 1
        if scenario == "evening":
            return 8 if elevator.bank == "low" else 16
        return 5 if elevator.bank == "low" else 14


def build_policy(name: str, weights: QueueWeights | None = None) -> DispatchPolicy:
    if name == "legacy_sticky":
        return LegacyStickyPolicy()
    if name == "collective":
        return CollectivePolicy()
    if name in {"queue_aware", "adaptive"}:
        return QueueAwarePolicy(weights=weights or QueueWeights(), name=name)
    raise ValueError(f"Unknown policy: {name}")

