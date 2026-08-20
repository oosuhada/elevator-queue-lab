from __future__ import annotations

import math
import random
from collections import defaultdict

from .demand import DemandModel
from .domain import Elevator, HallCall, Metrics, Passenger, SimulationConfig
from .policies import DispatchPolicy, QueueWeights, build_policy


class ElevatorSimulation:
    def __init__(
        self,
        scenario: str = "morning",
        policy_name: str = "queue_aware",
        seed: int = 7,
        weights: QueueWeights | None = None,
        config: SimulationConfig | None = None,
    ) -> None:
        self.config = config or SimulationConfig()
        self.scenario = scenario
        self.seed = seed
        self.random = random.Random(seed + 1000)
        self.demand = DemandModel(scenario, seed)
        self.policy_name = policy_name
        self.policy: DispatchPolicy = build_policy(policy_name, weights)
        self.sim_time = 0.0
        self.clock_start = self.demand.start_seconds
        self.next_passenger_id = 1
        self.waiting: list[Passenger] = []
        self.hall_calls: dict[tuple[int, int, str], HallCall] = {}
        self.metrics = Metrics()
        self.elevators = self._make_elevators()
        self.history: list[dict[str, float | int]] = []

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
        for _ in range(seconds):
            self.sim_time += 1.0
            self._expire_sticky_blocks()
            self._generate_demand()
            self._dispatch_calls()
            for elevator in self.elevators:
                self._move_elevator(elevator, 1.0)
            self._dispatch_calls()
            self.metrics.queue_samples.append(len(self.waiting))
            if int(self.sim_time) % 15 == 0:
                metric = self.metrics.snapshot(self.sim_time)
                metric["sim_time"] = int(self.sim_time)
                self.history.append(metric)
                if len(self.history) > 240:
                    self.history = self.history[-240:]

    def run(self, seconds: int) -> dict[str, float | int]:
        self.step(seconds)
        return self.metrics.snapshot(self.sim_time)

    def _generate_demand(self) -> None:
        for _ in range(self.demand.arrivals_this_second()):
            origin, destination = self.demand.trip()
            passenger = Passenger(
                passenger_id=self.next_passenger_id,
                origin=origin,
                destination=destination,
                created_at=self.sim_time,
            )
            self.next_passenger_id += 1
            self.waiting.append(passenger)
            self.metrics.arrival_count += 1
            bank = self._bank_for_trip(origin, destination)
            key = (origin, passenger.direction, bank)
            if key not in self.hall_calls:
                self.hall_calls[key] = HallCall(
                    floor=origin,
                    direction=passenger.direction,
                    bank=bank,
                    created_at=self.sim_time,
                )

    def _dispatch_calls(self) -> None:
        for key, call in list(self.hall_calls.items()):
            if not self._waiting_for_call(key):
                self.hall_calls.pop(key, None)
                continue
            if call.assigned_elevator is not None or call.blocked_until > self.sim_time:
                continue

            candidates = self._trip_compatible_candidates(key)
            chosen = self.policy.choose(call, candidates)
            if chosen is None:
                continue
            call.assigned_elevator = chosen.elevator_id
            chosen.add_stop(call.floor)

    def _trip_compatible_candidates(self, key: tuple[int, int, str]) -> list[Elevator]:
        floor, direction, bank = key
        passengers = [
            passenger
            for passenger in self.waiting
            if passenger.origin == floor
            and passenger.direction == direction
            and self._bank_for_trip(passenger.origin, passenger.destination) == bank
        ]
        if not passengers:
            return []
        destinations = {passenger.destination for passenger in passengers}
        compatible = [
            elevator
            for elevator in self.elevators
            if elevator.bank == bank
            and any(elevator.can_serve_trip(floor, destination) for destination in destinations)
        ]
        return compatible

    def _move_elevator(self, elevator: Elevator, dt: float) -> None:
        if elevator.door_timer > 0:
            elevator.door_timer = max(0.0, elevator.door_timer - dt)
            return

        self._remove_stale_pickup_stops(elevator)
        if not elevator.stops:
            self._maybe_reposition(elevator)
        if not elevator.stops:
            elevator.direction = 0
            return

        target = elevator.stops[0]
        delta = target - elevator.floor
        if abs(delta) < 1e-9:
            self._service_floor(elevator, target)
            return

        elevator.direction = 1 if delta > 0 else -1
        movement = dt / self.config.travel_seconds_per_floor
        old_floor = elevator.floor
        if abs(delta) <= movement:
            elevator.floor = float(target)
        else:
            elevator.floor += elevator.direction * movement
        elevator.distance_travelled += abs(elevator.floor - old_floor)

        if math.isclose(elevator.floor, float(target), abs_tol=1e-9):
            self._service_floor(elevator, target)

    def _service_floor(self, elevator: Elevator, floor: int) -> None:
        if elevator.stops and elevator.stops[0] == floor:
            elevator.stops.pop(0)

        remaining_onboard: list[Passenger] = []
        for passenger in elevator.onboard:
            if passenger.destination == floor:
                passenger.arrived_at = self.sim_time
                self.metrics.served_count += 1
                if passenger.boarded_at is not None:
                    self.metrics.ride_times.append(self.sim_time - passenger.boarded_at)
            else:
                remaining_onboard.append(passenger)
        elevator.onboard = remaining_onboard

        available = elevator.capacity - len(elevator.onboard)
        boarded_any = False
        waiting_after: list[Passenger] = []
        blocked_calls: set[tuple[int, int, str]] = set()
        for passenger in self.waiting:
            key = (
                passenger.origin,
                passenger.direction,
                self._bank_for_trip(passenger.origin, passenger.destination),
            )
            call = self.hall_calls.get(key)
            assigned_here = call is not None and call.assigned_elevator == elevator.elevator_id
            if (
                passenger.origin == floor
                and assigned_here
                and elevator.can_serve_trip(passenger.origin, passenger.destination)
                and available > 0
            ):
                passenger.boarded_at = self.sim_time
                self.metrics.wait_times.append(self.sim_time - passenger.created_at)
                elevator.onboard.append(passenger)
                elevator.add_stop(passenger.destination)
                available -= 1
                boarded_any = True
            else:
                if passenger.origin == floor and assigned_here and available <= 0:
                    blocked_calls.add(key)
                waiting_after.append(passenger)
        self.waiting = waiting_after

        for key in blocked_calls:
            call = self.hall_calls.get(key)
            if call is None:
                continue
            call.missed_count += 1
            self.metrics.missed_capacity += 1
            call.assigned_elevator = None
            if not self.policy.immediate_reassignment:
                call.blocked_until = self.sim_time + 8.0

        for key, call in list(self.hall_calls.items()):
            if call.floor != floor or call.assigned_elevator != elevator.elevator_id:
                continue
            if self._waiting_for_call(key):
                call.assigned_elevator = None
                if not self.policy.immediate_reassignment:
                    call.blocked_until = self.sim_time + 5.0
            else:
                self.hall_calls.pop(key, None)

        if boarded_any or floor in {passenger.destination for passenger in remaining_onboard}:
            elevator.door_timer = self.config.door_dwell_seconds
        else:
            # Pickup stops still open their doors even when the queue vanished a moment ago.
            elevator.door_timer = self.config.door_dwell_seconds

        self._sort_route(elevator)

    def _sort_route(self, elevator: Elevator) -> None:
        if not elevator.stops:
            return
        if elevator.direction > 0:
            above = sorted(stop for stop in elevator.stops if stop >= elevator.floor)
            below = sorted((stop for stop in elevator.stops if stop < elevator.floor), reverse=True)
            elevator.stops = above + below
        elif elevator.direction < 0:
            below = sorted((stop for stop in elevator.stops if stop <= elevator.floor), reverse=True)
            above = sorted(stop for stop in elevator.stops if stop > elevator.floor)
            elevator.stops = below + above

    def _remove_stale_pickup_stops(self, elevator: Elevator) -> None:
        if not elevator.stops:
            return
        cleaned: list[int] = []
        destinations = {passenger.destination for passenger in elevator.onboard}
        for stop in elevator.stops:
            is_destination = stop in destinations
            is_assigned_pickup = any(
                call.floor == stop and call.assigned_elevator == elevator.elevator_id
                for call in self.hall_calls.values()
            )
            is_parking = not elevator.onboard and not self.hall_calls
            if is_destination or is_assigned_pickup or is_parking:
                cleaned.append(stop)
        elevator.stops = cleaned

    def _maybe_reposition(self, elevator: Elevator) -> None:
        if elevator.onboard or any(
            call.assigned_elevator == elevator.elevator_id for call in self.hall_calls.values()
        ):
            return
        target = self.policy.parking_floor(elevator, self.scenario)
        if target is None or not elevator.can_serve_floor(target):
            return
        if abs(elevator.floor - target) >= 1.0:
            elevator.add_stop(target)

    def _expire_sticky_blocks(self) -> None:
        for call in self.hall_calls.values():
            if call.blocked_until <= self.sim_time and call.assigned_elevator is None:
                call.blocked_until = 0.0

    def _waiting_for_call(self, key: tuple[int, int, str]) -> bool:
        floor, direction, bank = key
        return any(
            passenger.origin == floor
            and passenger.direction == direction
            and self._bank_for_trip(passenger.origin, passenger.destination) == bank
            for passenger in self.waiting
        )

    def _bank_for_trip(self, origin: int, destination: int) -> str:
        non_lobby_floor = destination if origin == 1 else origin
        return "low" if non_lobby_floor <= self.config.low_zone_max else "high"

    def snapshot(self) -> dict[str, object]:
        floor_queues: dict[int, dict[str, int]] = defaultdict(lambda: {"up": 0, "down": 0})
        for passenger in self.waiting:
            floor_queues[passenger.origin]["up" if passenger.direction > 0 else "down"] += 1

        clock_seconds = (self.clock_start + int(self.sim_time)) % (24 * 3600)
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
            "weights": getattr(getattr(self.policy, "weights", None), "as_dict", lambda: {})(),
            "elevators": [
                {
                    "id": elevator.elevator_id,
                    "bank": elevator.bank,
                    "floor": round(elevator.floor, 2),
                    "direction": elevator.direction,
                    "load": len(elevator.onboard),
                    "capacity": elevator.capacity,
                    "stops": list(elevator.stops),
                    "door_open": elevator.door_timer > 0,
                }
                for elevator in self.elevators
            ],
            "queues": {str(floor): counts for floor, counts in floor_queues.items()},
            "calls": [
                {
                    "floor": call.floor,
                    "direction": call.direction,
                    "bank": call.bank,
                    "assigned": call.assigned_elevator,
                    "wait": round(self.sim_time - call.created_at, 1),
                    "missed": call.missed_count,
                }
                for call in self.hall_calls.values()
            ],
            "history": list(self.history),
        }

