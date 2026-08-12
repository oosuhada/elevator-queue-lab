from __future__ import annotations

from dataclasses import dataclass
from math import inf
from typing import Iterable

from .domain import Elevator, HallCall, SimulationConfig
from .physics import MotionProfile


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    elevator_id: str
    pickup_eta: float
    route_cost: float
    projected_load: int
    residual_capacity: int
    insertion_index: int
    score: float
    feasible: bool
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "elevator_id": self.elevator_id,
            "pickup_eta": round(self.pickup_eta, 3),
            "route_cost": round(self.route_cost, 3),
            "projected_load": self.projected_load,
            "residual_capacity": self.residual_capacity,
            "insertion_index": self.insertion_index,
            "score": round(self.score, 3),
            "feasible": self.feasible,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class DispatchDecision:
    chosen_elevator_id: str | None
    evaluations: tuple[CandidateEvaluation, ...]
    reason: str

    def evaluation_for(self, elevator_id: str | None) -> CandidateEvaluation | None:
        if elevator_id is None:
            return None
        return next(
            (item for item in self.evaluations if item.elevator_id == elevator_id),
            None,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "chosen_elevator_id": self.chosen_elevator_id,
            "reason": self.reason,
            "candidates": [item.as_dict() for item in self.evaluations],
        }


@dataclass(frozen=True, slots=True)
class RouteEstimate:
    pickup_eta: float
    route_cost: float
    projected_load: int
    residual_capacity: int
    insertion_index: int


def travel_seconds(start_floor: float, end_floor: float, config: SimulationConfig) -> float:
    distance_m = abs(end_floor - start_floor) * config.floor_height_m
    return MotionProfile.build(
        distance_m,
        config.max_speed_mps,
        config.acceleration_mps2,
    ).duration_s


def _service_cycle_seconds(config: SimulationConfig) -> float:
    return (
        config.levelling_seconds
        + config.door_open_seconds
        + config.door_dwell_seconds
        + config.door_close_seconds
    )


def _committed_prefix(
    elevator: Elevator,
    config: SimulationConfig,
) -> tuple[float, float, list[int], int]:
    """Return start time/floor, remaining route and load after unavoidable current work."""

    route = list(elevator.stops)
    elapsed = 0.0
    start_floor = elevator.floor
    projected_load = len(elevator.onboard)

    if elevator.phase == "moving" and elevator.target_floor is not None:
        elapsed += max(0.0, elevator.travel_duration - elevator.travel_elapsed)
        start_floor = float(elevator.target_floor)
        projected_load -= sum(
            passenger.destination == elevator.target_floor for passenger in elevator.onboard
        )
        elapsed += _service_cycle_seconds(config)
        if route and route[0] == elevator.target_floor:
            route = route[1:]
    elif elevator.phase.startswith("door_"):
        elapsed += max(0.0, elevator.phase_timer)

    return elapsed, start_floor, route, max(0, projected_load)


def estimate_route_insertion(
    elevator: Elevator,
    pickup_floor: int,
    config: SimulationConfig,
) -> RouteEstimate:
    """Estimate best insertion ETA using the same kinematic model as the simulator.

    The currently-moving target is treated as committed work. Remaining stops are evaluated
    with the pickup inserted at every legal position. Projected load removes onboard riders
    whose destinations are serviced before or at the pickup floor. Future hall-call boarding
    is intentionally not guessed here; that uncertainty is handled by CAPR's reserve term.
    """

    committed_time, committed_floor, base_route, committed_load = _committed_prefix(
        elevator, config
    )
    if pickup_floor in base_route:
        insertion_positions = [base_route.index(pickup_floor)]
    else:
        insertion_positions = list(range(len(base_route) + 1))

    best: RouteEstimate | None = None
    for insertion_index in insertion_positions:
        route = list(base_route)
        if pickup_floor not in route:
            route.insert(insertion_index, pickup_floor)

        elapsed = committed_time
        current_floor = committed_floor
        projected_load = committed_load
        pickup_eta = inf
        load_at_pickup = projected_load

        for index, stop in enumerate(route):
            elapsed += travel_seconds(current_floor, float(stop), config)
            projected_load -= sum(
                passenger.destination == stop for passenger in elevator.onboard
            )
            projected_load = max(0, projected_load)
            if stop == pickup_floor and pickup_eta is inf:
                # Boarding occurs after leveling and door opening; alighters leave first.
                pickup_eta = elapsed + config.levelling_seconds + config.door_open_seconds
                load_at_pickup = projected_load
            elapsed += _service_cycle_seconds(config)
            current_floor = float(stop)

        if pickup_eta is inf:
            pickup_eta = committed_time + travel_seconds(
                committed_floor, float(pickup_floor), config
            ) + config.levelling_seconds + config.door_open_seconds

        residual = max(0, elevator.capacity - load_at_pickup)
        estimate = RouteEstimate(
            pickup_eta=pickup_eta,
            route_cost=elapsed,
            projected_load=load_at_pickup,
            residual_capacity=residual,
            insertion_index=insertion_index,
        )
        if best is None or (estimate.pickup_eta, estimate.route_cost) < (
            best.pickup_eta,
            best.route_cost,
        ):
            best = estimate

    if best is None:
        raise RuntimeError("route estimator produced no candidate")
    return best


def build_evaluation(
    elevator: Elevator,
    call: HallCall,
    config: SimulationConfig,
    *,
    queue_size: int,
    now: float,
    mode: str,
) -> CandidateEvaluation:
    estimate = estimate_route_insertion(elevator, call.floor, config)
    age = max(0.0, now - call.created_at)
    direction_mismatch = (
        1.0
        if elevator.direction != 0 and elevator.direction != call.direction
        else 0.0
    )
    reserve = config.capacity_reserve
    usable_capacity = max(0, estimate.residual_capacity - reserve)
    capacity_shortfall = max(0, queue_size - usable_capacity)

    if mode == "nearest":
        score = estimate.pickup_eta
    elif mode == "collective":
        score = (
            estimate.pickup_eta
            + 8.0 * direction_mismatch
            + 0.12 * estimate.route_cost
            + 10.0 * elevator.load_ratio
        )
    elif mode == "queue_aware":
        score = (
            estimate.pickup_eta
            + 0.18 * estimate.route_cost
            + 18.0 * elevator.load_ratio
            + 10.0 * direction_mismatch
            + 55.0 * (1 if estimate.residual_capacity <= reserve else 0)
        )
    elif mode == "capr":
        score = (
            estimate.pickup_eta
            + 0.15 * estimate.route_cost
            + 12.0 * elevator.load_ratio
            + 8.0 * direction_mismatch
            + 120.0 * capacity_shortfall
            - min(age, 180.0) * 0.08
        )
    else:
        raise ValueError(f"unknown dispatch evaluation mode: {mode}")

    feasible = estimate.residual_capacity > reserve
    if mode == "capr" and not feasible:
        score += 10_000.0

    reason = (
        f"ETA {estimate.pickup_eta:.1f}s; residual {estimate.residual_capacity}/"
        f"{elevator.capacity}; route {estimate.route_cost:.1f}s; age {age:.1f}s"
    )
    if not feasible:
        reason += "; predicted capacity exhausted"
    elif capacity_shortfall > 0:
        reason += f"; queue shortfall {capacity_shortfall}"

    return CandidateEvaluation(
        elevator_id=elevator.elevator_id,
        pickup_eta=estimate.pickup_eta,
        route_cost=estimate.route_cost,
        projected_load=estimate.projected_load,
        residual_capacity=estimate.residual_capacity,
        insertion_index=estimate.insertion_index,
        score=score,
        feasible=feasible,
        reason=reason,
    )


def choose_decision(
    call: HallCall,
    elevators: Iterable[Elevator],
    config: SimulationConfig,
    *,
    queue_size: int,
    now: float,
    mode: str,
) -> DispatchDecision:
    evaluations = tuple(
        build_evaluation(
            elevator,
            call,
            config,
            queue_size=queue_size,
            now=now,
            mode=mode,
        )
        for elevator in elevators
    )
    if not evaluations:
        return DispatchDecision(None, (), "no compatible elevator")

    eligible = evaluations
    if mode == "capr":
        feasible = tuple(item for item in evaluations if item.feasible)
        if feasible:
            eligible = feasible
    chosen = min(eligible, key=lambda item: (item.score, item.pickup_eta, item.elevator_id))
    return DispatchDecision(
        chosen_elevator_id=chosen.elevator_id,
        evaluations=evaluations,
        reason=f"{chosen.elevator_id} selected by {mode}: {chosen.reason}",
    )
