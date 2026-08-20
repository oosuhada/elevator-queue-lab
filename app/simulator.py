from __future__ import annotations

import math
import random
from collections import defaultdict

from .demand import DemandModel
from .dispatch import DispatchDecision
from .domain import Elevator, HallCall, Metrics, Passenger, SimulationConfig
from .events import EventLedger
from .physics import MotionProfile, service_dwell_seconds
from .policies import DispatchPolicy, QueueWeights, build_policy
from .trace import PassengerTrace


CallKey = tuple[int, int, str, int | None]


class ElevatorSimulation:
    def __init__(
        self,
        scenario: str = "morning",
        policy_name: str = "queue_aware",
        seed: int = 7,
        weights: QueueWeights | None = None,
        config: SimulationConfig | None = None,
        trace: PassengerTrace | None = None,
    ) -> None:
        self.config = config or SimulationConfig()
        self.scenario = scenario
        self.seed = seed
        self.random = random.Random(seed + 1000)
        self.demand = DemandModel(scenario, seed)
        if trace is not None and trace.scenario != scenario:
            raise ValueError("Passenger trace scenario must match simulation scenario")
        self.trace = trace
        self._trace_index = 0
        self._last_demand_second = 0
        self._last_sample_second = 0
        self.policy_name = policy_name
        self.policy: DispatchPolicy = build_policy(policy_name, weights)
        self.sim_time = 0.0
        self.clock_start = self.demand.start_seconds
        self.next_passenger_id = 1
        self.waiting: list[Passenger] = []
        self.hall_calls: dict[CallKey, HallCall] = {}
        self.metrics = Metrics()
        self.ledger = EventLedger()
        self.elevators = self._make_elevators()
        self.history: list[dict[str, float | int]] = []
        self.decision_history: list[dict[str, object]] = []

    def _make_elevators(self) -> list[Elevator]:
        elevators: list[Elevator] = []
        for index in range(self.config.elevators_per_bank):
            elevators.append(
                Elevator(
                    elevator_id=f"L{index + 1}",
                    bank="low",
                    floor=float(1 + index * 3),
                    capacity=self.config.elevator_capacity,
                )
            )
        high_starts = [1.0, 14.0, 16.0]
        for index in range(self.config.elevators_per_bank):
            elevators.append(
                Elevator(
                    elevator_id=f"H{index + 1}",
                    bank="high",
                    floor=high_starts[index % len(high_starts)],
                    capacity=self.config.elevator_capacity,
                )
            )
        return elevators

    def step(self, seconds: int = 1) -> None:
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        end_time = self.sim_time + seconds
        while self.sim_time + 1e-9 < end_time:
            dt = min(self.config.time_step_seconds, end_time - self.sim_time)
            self.sim_time = round(self.sim_time + dt, 9)
            self._generate_due_demand()
            self._expire_impatient_passengers()
            self._expire_sticky_blocks()
            self._dispatch_calls()
            for elevator in self.elevators:
                self._advance_elevator(elevator, dt)
            self._dispatch_calls()
            self._sample_due_metrics()

    def run(self, seconds: int) -> dict[str, float | int]:
        self.step(seconds)
        return self.metrics.snapshot(self.sim_time)

    def _generate_due_demand(self) -> None:
        current_second = int(self.sim_time + 1e-9)
        while self._last_demand_second < current_second:
            self._last_demand_second += 1
            self._generate_demand_for_second(self._last_demand_second)

    def _generate_demand_for_second(self, second: int) -> None:
        if self.trace is not None:
            while self._trace_index < len(self.trace.events):
                event = self.trace.events[self._trace_index]
                if event.at > second:
                    break
                if event.at == second:
                    self._create_passenger(
                        event.passenger_id,
                        event.origin,
                        event.destination,
                        created_at=float(second),
                    )
                self._trace_index += 1
            return

        for _ in range(self.demand.arrivals_this_second()):
            origin, destination = self.demand.trip()
            self._create_passenger(
                self.next_passenger_id,
                origin,
                destination,
                created_at=float(second),
            )
            self.next_passenger_id += 1

    def _create_passenger(
        self,
        passenger_id: int,
        origin: int,
        destination: int,
        *,
        created_at: float,
    ) -> None:
        passenger = Passenger(
            passenger_id=passenger_id,
            origin=origin,
            destination=destination,
            created_at=created_at,
        )
        self.next_passenger_id = max(self.next_passenger_id, passenger_id + 1)
        self.waiting.append(passenger)
        self.metrics.arrival_count += 1
        bank = self._bank_for_trip(origin, destination)
        self.ledger.record(
            created_at,
            "arrival",
            passenger_id=passenger_id,
            floor=origin,
            bank=bank,
            details={"destination": destination},
        )
        key = self._call_key_for_passenger(passenger)
        if key not in self.hall_calls:
            self.hall_calls[key] = HallCall(
                floor=origin,
                direction=passenger.direction,
                bank=bank,
                destination=key[3],
                created_at=created_at,
            )

    def _dispatch_calls(self) -> None:
        for key, call in list(self.hall_calls.items()):
            if not self._waiting_for_call(key):
                self.hall_calls.pop(key, None)
                continue
            if call.blocked_until > self.sim_time:
                continue

            continuous = getattr(self.policy, "continuous_reassignment", False)
            if call.assigned_elevator is not None:
                if not continuous:
                    continue
                if (
                    self.sim_time - call.last_evaluated_at
                    < self.config.reassignment_interval_seconds
                ):
                    continue

            candidates = self._trip_compatible_candidates(key)
            if not candidates:
                continue
            decision = self.policy.decide(
                call,
                candidates,
                self.config,
                queue_size=self._queue_size(key),
                now=self.sim_time,
            )
            call.last_evaluated_at = self.sim_time
            self._record_decision(call, decision, self._queue_size(key))

            if call.assigned_elevator is None:
                self._apply_assignment(call, decision)
                continue
            self._consider_reassignment(call, decision)

    def _record_decision(
        self,
        call: HallCall,
        decision: DispatchDecision,
        queue_size: int,
    ) -> None:
        payload = {
            "sim_time": round(self.sim_time, 3),
            "floor": call.floor,
            "direction": call.direction,
            "bank": call.bank,
            "destination": call.destination,
            "queue_size": queue_size,
            "current_assignment": call.assigned_elevator,
            **decision.as_dict(),
        }
        self.decision_history.append(payload)
        if len(self.decision_history) > 200:
            self.decision_history = self.decision_history[-200:]
        self.ledger.record(
            self.sim_time,
            "dispatch_decision",
            elevator_id=decision.chosen_elevator_id,
            floor=call.floor,
            bank=call.bank,
            details=payload,
        )

    def _apply_assignment(
        self,
        call: HallCall,
        decision: DispatchDecision,
        *,
        prior_elevator: str | None = None,
    ) -> None:
        chosen_id = decision.chosen_elevator_id
        if chosen_id is None:
            return
        chosen = self._find_elevator(chosen_id)
        evaluation = decision.evaluation_for(chosen_id)
        prior = prior_elevator or call.last_assigned_elevator
        call.assigned_elevator = chosen_id
        call.last_assigned_elevator = chosen_id
        call.assigned_at = self.sim_time
        call.assigned_score = evaluation.score if evaluation is not None else None
        chosen.add_stop(call.floor)
        event_kind = "reassign" if prior is not None and prior != chosen_id else "assign"
        if event_kind == "reassign":
            self.metrics.reassignment_count += 1
        else:
            self.metrics.assignment_count += 1
        self.ledger.record(
            self.sim_time,
            event_kind,
            elevator_id=chosen_id,
            floor=call.floor,
            bank=call.bank,
            details={
                "direction": call.direction,
                "destination": call.destination,
                "previous_elevator": prior,
                "missed_count": call.missed_count,
                "score": evaluation.score if evaluation is not None else None,
                "decision_reason": decision.reason,
            },
        )

    def _consider_reassignment(
        self,
        call: HallCall,
        decision: DispatchDecision,
    ) -> None:
        assigned_id = call.assigned_elevator
        chosen_id = decision.chosen_elevator_id
        if assigned_id is None or chosen_id is None:
            return
        assigned_eval = decision.evaluation_for(assigned_id)
        chosen_eval = decision.evaluation_for(chosen_id)
        if chosen_id == assigned_id:
            if assigned_eval is not None:
                call.assigned_score = assigned_eval.score
            return

        assignment_age = (
            self.sim_time - call.assigned_at if call.assigned_at is not None else math.inf
        )
        assigned_infeasible = assigned_eval is None or not assigned_eval.feasible
        score_gain = (
            math.inf
            if assigned_eval is None or chosen_eval is None
            else assigned_eval.score - chosen_eval.score
        )
        cooldown_elapsed = assignment_age >= self.config.reassignment_cooldown_seconds
        materially_better = score_gain >= self.config.reassignment_min_gain
        if not assigned_infeasible and not (cooldown_elapsed and materially_better):
            return

        old_id = assigned_id
        self._remove_pickup_stop_if_unneeded(old_id, call)
        call.assigned_elevator = None
        call.assigned_score = None
        self.metrics.invalidation_count += 1
        reason = (
            "predicted_capacity_exhausted"
            if assigned_infeasible
            else f"better_candidate_gain={score_gain:.3f}"
        )
        self.ledger.record(
            self.sim_time,
            "assignment_invalidated",
            elevator_id=old_id,
            floor=call.floor,
            bank=call.bank,
            details={
                "reason": reason,
                "replacement": chosen_id,
                "assigned_candidate": assigned_eval.as_dict() if assigned_eval else None,
                "replacement_candidate": chosen_eval.as_dict() if chosen_eval else None,
            },
        )
        self._apply_assignment(call, decision, prior_elevator=old_id)

    def _remove_pickup_stop_if_unneeded(self, elevator_id: str, call: HallCall) -> None:
        elevator = self._find_elevator(elevator_id)
        if call.floor in {passenger.destination for passenger in elevator.onboard}:
            return
        if any(
            other is not call
            and other.assigned_elevator == elevator_id
            and other.floor == call.floor
            for other in self.hall_calls.values()
        ):
            return
        elevator.stops = [stop for stop in elevator.stops if stop != call.floor]

    def _find_elevator(self, elevator_id: str) -> Elevator:
        elevator = next(
            (item for item in self.elevators if item.elevator_id == elevator_id),
            None,
        )
        if elevator is None:
            raise RuntimeError(f"unknown elevator: {elevator_id}")
        return elevator

    def _trip_compatible_candidates(self, key: CallKey) -> list[Elevator]:
        floor, direction, bank, destination_key = key
        passengers = [
            passenger
            for passenger in self.waiting
            if passenger.origin == floor
            and passenger.direction == direction
            and self._bank_for_trip(passenger.origin, passenger.destination) == bank
            and (destination_key is None or passenger.destination == destination_key)
        ]
        if not passengers:
            return []
        destinations = {passenger.destination for passenger in passengers}
        return [
            elevator
            for elevator in self.elevators
            if elevator.bank == bank
            and any(
                elevator.can_serve_trip(floor, destination)
                for destination in destinations
            )
        ]

    def _advance_elevator(self, elevator: Elevator, dt: float) -> None:
        if elevator.phase == "idle":
            self._remove_stale_pickup_stops(elevator)
            if not elevator.stops:
                self._maybe_reposition(elevator)
            if not elevator.stops:
                elevator.direction = 0
                return
            self._begin_trip(elevator, elevator.stops[0])

        if elevator.phase == "moving":
            self._advance_motion(elevator, dt)
            return

        if elevator.phase.startswith("door_"):
            self._advance_door_phase(elevator, dt)

    def _begin_trip(self, elevator: Elevator, target: int) -> None:
        elevator.target_floor = target
        delta_floors = target - elevator.floor
        if abs(delta_floors) < 1e-9:
            elevator.phase = "door_opening"
            elevator.phase_timer = (
                self.config.levelling_seconds + self.config.door_open_seconds
            )
            return

        elevator.direction = 1 if delta_floors > 0 else -1
        distance_m = abs(delta_floors) * self.config.floor_height_m
        profile = MotionProfile.build(
            distance_m,
            self.config.max_speed_mps,
            self.config.acceleration_mps2,
        )
        elevator.phase = "moving"
        elevator.travel_start_floor = elevator.floor
        elevator.travel_elapsed = 0.0
        elevator.travel_duration = profile.duration_s
        self.ledger.record(
            self.sim_time,
            "car_depart",
            elevator_id=elevator.elevator_id,
            floor=int(round(elevator.floor)),
            bank=elevator.bank,
            details={
                "target_floor": target,
                "travel_duration": round(profile.duration_s, 4),
            },
        )

    def _advance_motion(self, elevator: Elevator, dt: float) -> None:
        if elevator.target_floor is None or elevator.travel_start_floor is None:
            raise RuntimeError("moving elevator has no travel target")
        start = elevator.travel_start_floor
        target = elevator.target_floor
        distance_m = abs(target - start) * self.config.floor_height_m
        profile = MotionProfile.build(
            distance_m,
            self.config.max_speed_mps,
            self.config.acceleration_mps2,
        )
        old_floor = elevator.floor
        elevator.travel_elapsed = min(
            profile.duration_s,
            elevator.travel_elapsed + dt,
        )
        fraction = profile.fraction_at(elevator.travel_elapsed)
        elevator.floor = start + (target - start) * fraction
        elevator.distance_travelled += abs(elevator.floor - old_floor)

        if elevator.travel_elapsed + 1e-9 >= profile.duration_s:
            elevator.floor = float(target)
            elevator.phase = "door_opening"
            elevator.phase_timer = (
                self.config.levelling_seconds + self.config.door_open_seconds
            )
            self.ledger.record(
                self.sim_time,
                "car_arrive",
                elevator_id=elevator.elevator_id,
                floor=target,
                bank=elevator.bank,
            )

    def _advance_door_phase(self, elevator: Elevator, dt: float) -> None:
        elevator.phase_timer = max(0.0, elevator.phase_timer - dt)
        if elevator.phase_timer > 1e-9:
            return

        if elevator.phase == "door_opening":
            if elevator.target_floor is None:
                raise RuntimeError("door opening without a target floor")
            transfer_count = self._service_floor(elevator, elevator.target_floor)
            elevator.phase = "door_dwell"
            elevator.phase_timer = service_dwell_seconds(
                transfer_count,
                self.config.door_dwell_seconds,
                self.config.passenger_transfer_seconds,
            )
            return

        if elevator.phase == "door_dwell":
            elevator.phase = "door_closing"
            elevator.phase_timer = self.config.door_close_seconds
            return

        if elevator.phase == "door_closing":
            elevator.phase = "idle"
            elevator.phase_timer = 0.0
            elevator.target_floor = None
            elevator.travel_start_floor = None
            elevator.travel_elapsed = 0.0
            elevator.travel_duration = 0.0
            if not elevator.stops:
                elevator.direction = 0
            return

    def _service_floor(self, elevator: Elevator, floor: int) -> int:
        if elevator.stops and elevator.stops[0] == floor:
            elevator.stops.pop(0)

        remaining_onboard: list[Passenger] = []
        alighted_count = 0
        for passenger in elevator.onboard:
            if passenger.destination == floor:
                passenger.arrived_at = self.sim_time
                self.metrics.served_count += 1
                alighted_count += 1
                if passenger.boarded_at is not None:
                    self.metrics.ride_times.append(
                        self.sim_time - passenger.boarded_at
                    )
                self.ledger.record(
                    self.sim_time,
                    "alight",
                    passenger_id=passenger.passenger_id,
                    elevator_id=elevator.elevator_id,
                    floor=floor,
                    bank=elevator.bank,
                )
            else:
                remaining_onboard.append(passenger)
        elevator.onboard = remaining_onboard

        available = elevator.capacity - len(elevator.onboard)
        boarded_count = 0
        waiting_after: list[Passenger] = []
        blocked_calls: set[CallKey] = set()
        for passenger in self.waiting:
            key = self._call_key_for_passenger(passenger)
            call = self.hall_calls.get(key)
            assigned_here = (
                call is not None
                and call.assigned_elevator == elevator.elevator_id
            )
            if (
                passenger.origin == floor
                and assigned_here
                and elevator.can_serve_trip(
                    passenger.origin,
                    passenger.destination,
                )
                and available > 0
            ):
                passenger.boarded_at = self.sim_time
                self.metrics.wait_times.append(
                    self.sim_time - passenger.created_at
                )
                elevator.onboard.append(passenger)
                elevator.add_stop(passenger.destination)
                available -= 1
                boarded_count += 1
                self.ledger.record(
                    self.sim_time,
                    "board",
                    passenger_id=passenger.passenger_id,
                    elevator_id=elevator.elevator_id,
                    floor=floor,
                    bank=elevator.bank,
                    details={"destination": passenger.destination},
                )
            else:
                if (
                    passenger.origin == floor
                    and assigned_here
                    and available <= 0
                ):
                    blocked_calls.add(key)
                waiting_after.append(passenger)
        self.waiting = waiting_after

        for key in blocked_calls:
            call = self.hall_calls.get(key)
            if call is None:
                continue
            call.missed_count += 1
            self.metrics.missed_capacity += 1
            self.ledger.record(
                self.sim_time,
                "full_pass",
                elevator_id=elevator.elevator_id,
                floor=call.floor,
                bank=call.bank,
                details={
                    "direction": call.direction,
                    "destination": call.destination,
                    "missed_count": call.missed_count,
                },
            )
            call.assigned_elevator = None
            call.assigned_at = None
            call.assigned_score = None
            if not self.policy.immediate_reassignment:
                call.blocked_until = self.sim_time + 8.0

        for key, call in list(self.hall_calls.items()):
            if (
                call.floor != floor
                or call.assigned_elevator != elevator.elevator_id
            ):
                continue
            if self._waiting_for_call(key):
                call.assigned_elevator = None
                call.assigned_at = None
                call.assigned_score = None
                if not self.policy.immediate_reassignment:
                    call.blocked_until = self.sim_time + 5.0
            else:
                self.hall_calls.pop(key, None)

        self._sort_route(elevator)
        return boarded_count + alighted_count

    def _sort_route(self, elevator: Elevator) -> None:
        if not elevator.stops:
            return
        if elevator.direction > 0:
            above = sorted(
                stop for stop in elevator.stops if stop >= elevator.floor
            )
            below = sorted(
                (stop for stop in elevator.stops if stop < elevator.floor),
                reverse=True,
            )
            elevator.stops = above + below
        elif elevator.direction < 0:
            below = sorted(
                (stop for stop in elevator.stops if stop <= elevator.floor),
                reverse=True,
            )
            above = sorted(
                stop for stop in elevator.stops if stop > elevator.floor
            )
            elevator.stops = below + above

    def _remove_stale_pickup_stops(self, elevator: Elevator) -> None:
        if not elevator.stops:
            return
        cleaned: list[int] = []
        destinations = {passenger.destination for passenger in elevator.onboard}
        for stop in elevator.stops:
            is_destination = stop in destinations
            is_assigned_pickup = any(
                call.floor == stop
                and call.assigned_elevator == elevator.elevator_id
                for call in self.hall_calls.values()
            )
            is_parking = not elevator.onboard and not self.hall_calls
            if is_destination or is_assigned_pickup or is_parking:
                cleaned.append(stop)
        elevator.stops = cleaned

    def _maybe_reposition(self, elevator: Elevator) -> None:
        if elevator.onboard or any(
            call.assigned_elevator == elevator.elevator_id
            for call in self.hall_calls.values()
        ):
            return
        target = self.policy.parking_floor(elevator, self.scenario)
        if target is None or not elevator.can_serve_floor(target):
            return
        if abs(elevator.floor - target) >= 1.0:
            elevator.add_stop(target)
            self.ledger.record(
                self.sim_time,
                "parking_move",
                elevator_id=elevator.elevator_id,
                floor=target,
                bank=elevator.bank,
            )

    def _expire_sticky_blocks(self) -> None:
        for call in self.hall_calls.values():
            if (
                call.blocked_until <= self.sim_time
                and call.assigned_elevator is None
            ):
                call.blocked_until = 0.0

    def _expire_impatient_passengers(self) -> None:
        patience = self.config.passenger_patience_seconds
        if patience is None:
            return
        kept: list[Passenger] = []
        for passenger in self.waiting:
            waited = self.sim_time - passenger.created_at
            if waited + 1e-9 < patience:
                kept.append(passenger)
                continue
            self.metrics.abandoned_count += 1
            bank = self._bank_for_trip(
                passenger.origin,
                passenger.destination,
            )
            self.ledger.record(
                self.sim_time,
                "abandon",
                passenger_id=passenger.passenger_id,
                floor=passenger.origin,
                bank=bank,
                details={
                    "destination": passenger.destination,
                    "waited": round(waited, 4),
                },
            )
        self.waiting = kept

    def _waiting_for_call(self, key: CallKey) -> bool:
        return any(
            self._call_key_for_passenger(passenger) == key
            for passenger in self.waiting
        )

    def _queue_size(self, key: CallKey) -> int:
        return sum(
            self._call_key_for_passenger(passenger) == key
            for passenger in self.waiting
        )

    def _call_key_for_passenger(self, passenger: Passenger) -> CallKey:
        bank = self._bank_for_trip(
            passenger.origin,
            passenger.destination,
        )
        destination = (
            passenger.destination
            if self.config.control_mode == "destination"
            else None
        )
        return (
            passenger.origin,
            passenger.direction,
            bank,
            destination,
        )

    def _bank_for_trip(self, origin: int, destination: int) -> str:
        non_lobby_floor = destination if origin == 1 else origin
        return (
            "low"
            if non_lobby_floor <= self.config.low_zone_max
            else "high"
        )

    def _sample_due_metrics(self) -> None:
        current_second = int(self.sim_time + 1e-9)
        while self._last_sample_second < current_second:
            self._last_sample_second += 1
            self.metrics.queue_samples.append(len(self.waiting))
            if self._last_sample_second % 15 == 0:
                metric = self.metrics.snapshot(float(self._last_sample_second))
                metric["sim_time"] = self._last_sample_second
                self.history.append(metric)
                if len(self.history) > 240:
                    self.history = self.history[-240:]

    def audit(self) -> dict[str, object]:
        event_counts = self.ledger.counts()
        onboard = sum(len(elevator.onboard) for elevator in self.elevators)
        waiting = len(self.waiting)
        arrived = self.metrics.arrival_count
        served = self.metrics.served_count
        abandoned = self.metrics.abandoned_count
        boarded = len(self.metrics.wait_times)
        violations: list[str] = []
        if arrived != waiting + onboard + served + abandoned:
            violations.append("passenger_conservation")
        if boarded != onboard + served:
            violations.append("boarded_conservation")
        if event_counts.get("arrival", 0) != arrived:
            violations.append("arrival_event_count")
        if event_counts.get("board", 0) != boarded:
            violations.append("board_event_count")
        if event_counts.get("alight", 0) != served:
            violations.append("alight_event_count")
        if event_counts.get("abandon", 0) != abandoned:
            violations.append("abandon_event_count")
        if event_counts.get("assign", 0) != self.metrics.assignment_count:
            violations.append("assignment_event_count")
        if event_counts.get("reassign", 0) != self.metrics.reassignment_count:
            violations.append("reassignment_event_count")
        if (
            event_counts.get("assignment_invalidated", 0)
            != self.metrics.invalidation_count
        ):
            violations.append("invalidation_event_count")
        if any(
            len(elevator.onboard) > elevator.capacity
            for elevator in self.elevators
        ):
            violations.append("capacity_overflow")
        if any(wait < 0 for wait in self.metrics.wait_times):
            violations.append("negative_wait_time")
        if any(ride < 0 for ride in self.metrics.ride_times):
            violations.append("negative_ride_time")
        if any(
            not (1.0 <= elevator.floor <= self.config.floors)
            for elevator in self.elevators
        ):
            violations.append("car_outside_building")
        return {
            "ok": not violations,
            "violations": violations,
            "arrivals": arrived,
            "waiting": waiting,
            "onboard": onboard,
            "served": served,
            "abandoned": abandoned,
            "boarded": boarded,
            "event_counts": event_counts,
        }

    def snapshot(self) -> dict[str, object]:
        floor_queues: dict[int, dict[str, int]] = defaultdict(
            lambda: {"up": 0, "down": 0}
        )
        for passenger in self.waiting:
            floor_queues[passenger.origin][
                "up" if passenger.direction > 0 else "down"
            ] += 1

        clock_seconds = (
            self.clock_start + int(self.sim_time)
        ) % (24 * 3600)
        hour = clock_seconds // 3600
        minute = (clock_seconds % 3600) // 60
        second = clock_seconds % 60
        metrics = self.metrics.snapshot(self.sim_time)
        metrics["current_queue"] = len(self.waiting)

        return {
            "scenario": self.scenario,
            "policy": self.policy_name,
            "sim_time": int(self.sim_time),
            "clock": f"{hour:02d}:{minute:02d}:{second:02d}",
            "metrics": metrics,
            "weights": getattr(
                getattr(self.policy, "weights", None),
                "as_dict",
                lambda: {},
            )(),
            "elevators": [
                {
                    "id": elevator.elevator_id,
                    "bank": elevator.bank,
                    "floor": round(elevator.floor, 2),
                    "direction": elevator.direction,
                    "load": len(elevator.onboard),
                    "capacity": elevator.capacity,
                    "stops": list(elevator.stops),
                    "door_open": elevator.phase
                    in {"door_opening", "door_dwell", "door_closing"},
                    "phase": elevator.phase,
                    "target_floor": elevator.target_floor,
                }
                for elevator in self.elevators
            ],
            "queues": {
                str(floor): counts
                for floor, counts in floor_queues.items()
            },
            "calls": [
                {
                    "floor": call.floor,
                    "direction": call.direction,
                    "bank": call.bank,
                    "destination": call.destination,
                    "assigned": call.assigned_elevator,
                    "wait": round(self.sim_time - call.created_at, 1),
                    "missed": call.missed_count,
                    "assigned_score": (
                        round(call.assigned_score, 3)
                        if call.assigned_score is not None
                        else None
                    ),
                }
                for call in self.hall_calls.values()
            ],
            "history": list(self.history),
            "audit": self.audit(),
            "event_tail": self.ledger.tail(),
            "decision_tail": self.decision_history[-20:],
            "trace_digest": (
                self.trace.digest if self.trace is not None else None
            ),
            "simulation_config": self.config.as_dict(),
        }
