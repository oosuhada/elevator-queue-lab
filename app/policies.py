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


def _hold_current(
    call: HallCall,
    decision: DispatchDecision,
    reason: str,
) -> DispatchDecision:
    return DispatchDecision(
        chosen_elevator_id=call.assigned_elevator,
        evaluations=decision.evaluations,
        reason=f"hold {call.assigned_elevator}: {reason}",
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
    """Capacity-Aware Predictive Reassignment controller."""

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
        base = choose_decision(
            call,
            elevators,
            config,
            queue_size=queue_size,
            now=now,
            mode="capr",
        )
        assigned_id = call.assigned_elevator
        chosen_id = base.chosen_elevator_id
        if assigned_id is None or chosen_id is None or assigned_id == chosen_id:
            return base

        assigned = base.evaluation_for(assigned_id)
        chosen = base.evaluation_for(chosen_id)
        if assigned is None:
            return base
        if chosen is None:
            return _hold_current(call, base, "replacement evaluation missing")

        # Capacity invalidation is the primary CAPR intervention. Reassign immediately only
        # when the replacement is actually feasible. If every car is predicted full, holding
        # the current owner is less harmful than ping-ponging between equally infeasible cars.
        if not assigned.feasible:
            if chosen.feasible:
                return base
            return _hold_current(call, base, "all compatible cars lack predicted pickup capacity")

        # For a feasible current car, require a meaningful ETA improvement in addition to
        # the simulator's score/cooldown gate. This makes reassignment an exception rather
        # than a continuously oscillating optimization of tiny score differences.
        assignment_age = now - call.assigned_at if call.assigned_at is not None else 0.0
        score_gain = assigned.score - chosen.score
        eta_gain = assigned.pickup_eta - chosen.pickup_eta
        if assignment_age < config.reassignment_cooldown_seconds:
            return _hold_current(call, base, f"cooldown {assignment_age:.1f}s")
        if score_gain < config.reassignment_min_gain:
            return _hold_current(call, base, f"score gain {score_gain:.1f} below threshold")
        if eta_gain < config.reassignment_min_eta_gain_seconds:
            return _hold_current(call, base, f"ETA gain {eta_gain:.1f}s below threshold")
        if call.reassignment_count >= config.max_noncapacity_reassignments_per_call:
            return _hold_current(call, base, "non-capacity reassignment budget exhausted")
        call.reassignment_count += 1
        return base

    def parking_floor(self, elevator: Elevator, scenario: str) -> int | None:
        if scenario == "morning":
            return 1
        if scenario == "lunch":
            return 1 if elevator.elevator_id.endswith("1") else (6 if elevator.bank == "low" else 14)
        if scenario == "evening":
            return 8 if elevator.bank == "low" else 16
        return 5 if elevator.bank == "low" else 14


def build_policy(
    name: str,
    weights: QueueWeights | None = None,
    *,
    scenario: str = "normal",
) -> DispatchPolicy:
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
    if name == "rl":
        from pathlib import Path

        from .learning import LearnedDispatchPolicy, load_model_artifact

        model_path = Path(__file__).resolve().parents[1] / "models" / "m5-ddqn-baseline.json"
        if not model_path.is_file():
            raise FileNotFoundError(
                "M5 learned policy artifact is unavailable; run scripts/run_m5_training.py first"
            )
        network, _ = load_model_artifact(model_path)
        return LearnedDispatchPolicy(network, scenario=scenario)
    raise ValueError(f"Unknown policy: {name}")
