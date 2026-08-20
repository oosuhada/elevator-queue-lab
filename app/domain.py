from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class Passenger:
    passenger_id: int
    origin: int
    destination: int
    created_at: float
    boarded_at: float | None = None
    arrived_at: float | None = None

    @property
    def direction(self) -> int:
        return 1 if self.destination > self.origin else -1


@dataclass(slots=True)
class HallCall:
    floor: int
    direction: int
    bank: str
    created_at: float
    destination: int | None = None
    assigned_elevator: str | None = None
    assigned_at: float | None = None
    assigned_score: float | None = None
    missed_count: int = 0
    blocked_until: float = 0.0
    last_assigned_elevator: str | None = None
    last_evaluated_at: float = 0.0
    reassignment_count: int = 0

    @property
    def key(self) -> tuple[int, int, str, int | None]:
        return (self.floor, self.direction, self.bank, self.destination)


@dataclass(slots=True)
class Elevator:
    elevator_id: str
    bank: str
    floor: float
    capacity: int = 14
    direction: int = 0
    stops: list[int] = field(default_factory=list)
    onboard: list[Passenger] = field(default_factory=list)
    distance_travelled: float = 0.0
    phase: str = "idle"
    phase_timer: float = 0.0
    target_floor: int | None = None
    travel_start_floor: float | None = None
    travel_elapsed: float = 0.0
    travel_duration: float = 0.0

    @property
    def load_ratio(self) -> float:
        return len(self.onboard) / self.capacity

    @property
    def door_timer(self) -> float:
        return self.phase_timer if self.phase.startswith("door_") else 0.0

    def can_serve_floor(self, floor: int) -> bool:
        if floor == 1:
            return True
        if self.bank == "low":
            return 2 <= floor <= 9
        return 10 <= floor <= 18

    def can_serve_trip(self, origin: int, destination: int) -> bool:
        return self.can_serve_floor(origin) and self.can_serve_floor(destination)

    def add_stop(self, floor: int) -> None:
        if floor not in self.stops and int(round(self.floor)) != floor:
            self.stops.append(floor)


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    floors: int = 18
    low_zone_max: int = 9
    high_zone_min: int = 10
    elevators_per_bank: int = 3
    elevator_capacity: int = 14
    floor_height_m: float = 3.6
    max_speed_mps: float = 2.5
    acceleration_mps2: float = 1.0
    levelling_seconds: float = 0.5
    door_open_seconds: float = 1.0
    door_dwell_seconds: float = 1.5
    door_close_seconds: float = 1.0
    passenger_transfer_seconds: float = 0.45
    time_step_seconds: float = 0.25
    passenger_patience_seconds: float | None = None
    control_mode: str = "conventional"
    reassignment_interval_seconds: float = 1.0
    reassignment_cooldown_seconds: float = 6.0
    reassignment_min_gain: float = 8.0
    reassignment_min_eta_gain_seconds: float = 5.0
    max_noncapacity_reassignments_per_call: int = 1
    capacity_reserve: int = 1

    def __post_init__(self) -> None:
        if self.control_mode not in {"conventional", "destination"}:
            raise ValueError("control_mode must be conventional or destination")
        if self.time_step_seconds <= 0:
            raise ValueError("time_step_seconds must be positive")
        if self.elevator_capacity <= 0:
            raise ValueError("elevator_capacity must be positive")
        if self.capacity_reserve < 0:
            raise ValueError("capacity_reserve cannot be negative")
        if self.reassignment_interval_seconds <= 0:
            raise ValueError("reassignment_interval_seconds must be positive")
        if self.reassignment_cooldown_seconds < 0:
            raise ValueError("reassignment_cooldown_seconds cannot be negative")
        if self.reassignment_min_gain < 0 or self.reassignment_min_eta_gain_seconds < 0:
            raise ValueError("reassignment gain thresholds cannot be negative")
        if self.max_noncapacity_reassignments_per_call < 0:
            raise ValueError("max_noncapacity_reassignments_per_call cannot be negative")

    def as_dict(self) -> dict[str, float | int | str | None]:
        return asdict(self)


@dataclass(slots=True)
class Metrics:
    wait_times: list[float] = field(default_factory=list)
    ride_times: list[float] = field(default_factory=list)
    queue_samples: list[int] = field(default_factory=list)
    arrival_count: int = 0
    served_count: int = 0
    missed_capacity: int = 0
    abandoned_count: int = 0
    assignment_count: int = 0
    reassignment_count: int = 0
    invalidation_count: int = 0

    def snapshot(self, elapsed_seconds: float) -> dict[str, float | int]:
        waits = sorted(self.wait_times)
        avg_wait = sum(waits) / len(waits) if waits else 0.0
        p95_wait = waits[min(len(waits) - 1, int(len(waits) * 0.95))] if waits else 0.0
        max_wait = waits[-1] if waits else 0.0
        avg_queue = (
            sum(self.queue_samples) / len(self.queue_samples)
            if self.queue_samples
            else 0.0
        )
        arrival_rate = self.arrival_count / elapsed_seconds if elapsed_seconds > 0 else 0.0
        littles_law = arrival_rate * avg_wait
        return {
            "avg_wait": round(avg_wait, 2),
            "p95_wait": round(p95_wait, 2),
            "max_wait": round(max_wait, 2),
            "avg_queue": round(avg_queue, 2),
            "little_law_lq": round(littles_law, 2),
            "arrival_rate_per_min": round(arrival_rate * 60, 2),
            "served": self.served_count,
            "arrivals": self.arrival_count,
            "missed_capacity": self.missed_capacity,
            "abandoned": self.abandoned_count,
            "assignments": self.assignment_count,
            "reassignments": self.reassignment_count,
            "invalidations": self.invalidation_count,
        }
