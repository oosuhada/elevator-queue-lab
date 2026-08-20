from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .demand import (
    HIGH_OFFICE_FLOORS,
    LOBBY_FLOOR,
    LOW_OFFICE_FLOORS,
    ROOFTOP_ACCESS_FLOOR,
)
from .trace import DemandEvent, PassengerTrace


@dataclass(frozen=True, slots=True)
class ParametricOfficeDemand:
    """Controlled demand surface used only for theory-extraction experiments.

    The production office-demand model deliberately remains scenario based.  M7 instead needs to
    vary one structural quantity at a time, so this specification exposes arrival intensity and
    lobby direction while keeping the trip-purpose mix explicit and reproducible.
    """

    arrivals_per_minute: float
    lobby_up_probability: float
    lobby_share: float = 0.85
    rooftop_share: float = 0.10
    interfloor_share: float = 0.05

    def __post_init__(self) -> None:
        if self.arrivals_per_minute <= 0:
            raise ValueError("arrivals_per_minute must be positive")
        if not 0.0 <= self.lobby_up_probability <= 1.0:
            raise ValueError("lobby_up_probability must be between 0 and 1")
        shares = (self.lobby_share, self.rooftop_share, self.interfloor_share)
        if any(share < 0.0 for share in shares):
            raise ValueError("trip-purpose shares cannot be negative")
        if not math.isclose(sum(shares), 1.0, abs_tol=1e-9):
            raise ValueError("trip-purpose shares must sum to 1")

    @property
    def directional_mixing_index(self) -> float:
        """Bernoulli mixing term, 0 for one-way traffic and 1 for a 50/50 lobby stream."""

        p = self.lobby_up_probability
        return 4.0 * p * (1.0 - p)

    @property
    def bidirectional_load_rate(self) -> float:
        """Passenger/minute load weighted by simultaneous opposite-direction opportunity."""

        return self.arrivals_per_minute * self.directional_mixing_index

    def as_dict(self) -> dict[str, float]:
        return {
            "arrivals_per_minute": self.arrivals_per_minute,
            "lobby_up_probability": self.lobby_up_probability,
            "lobby_share": self.lobby_share,
            "rooftop_share": self.rooftop_share,
            "interfloor_share": self.interfloor_share,
            "directional_mixing_index": round(self.directional_mixing_index, 6),
            "bidirectional_load_rate": round(self.bidirectional_load_rate, 6),
        }


def generate_parametric_trace(
    spec: ParametricOfficeDemand,
    duration_seconds: int,
    seed: int,
    *,
    scenario: str = "normal",
) -> PassengerTrace:
    """Generate a deterministic passenger trace from a controlled M7 demand specification."""

    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    rng = random.Random(seed)
    events: list[DemandEvent] = []
    passenger_id = 1
    rate = spec.arrivals_per_minute / 60.0

    for second in range(1, duration_seconds + 1):
        for _ in range(_poisson_count(rng, rate)):
            origin, destination = _trip(rng, spec)
            events.append(
                DemandEvent(
                    at=second,
                    passenger_id=passenger_id,
                    origin=origin,
                    destination=destination,
                )
            )
            passenger_id += 1

    return PassengerTrace(
        scenario=scenario,
        seed=seed,
        duration_seconds=duration_seconds,
        events=tuple(events),
    )


def _poisson_count(rng: random.Random, rate: float) -> int:
    threshold = math.exp(-rate)
    product = 1.0
    count = 0
    while product > threshold:
        product *= rng.random()
        count += 1
    return max(0, count - 1)


def _trip(rng: random.Random, spec: ParametricOfficeDemand) -> tuple[int, int]:
    roll = rng.random()
    if roll < spec.lobby_share:
        office = _office_floor(rng)
        if rng.random() < spec.lobby_up_probability:
            return LOBBY_FLOOR, office
        return office, LOBBY_FLOOR
    if roll < spec.lobby_share + spec.rooftop_share:
        office = rng.choice(HIGH_OFFICE_FLOORS)
        if rng.random() < 0.5:
            return office, ROOFTOP_ACCESS_FLOOR
        return ROOFTOP_ACCESS_FLOOR, office
    return _same_bank_trip(rng)


def _office_floor(rng: random.Random) -> int:
    if rng.random() < 0.46:
        return rng.choice(LOW_OFFICE_FLOORS)
    return rng.choice(HIGH_OFFICE_FLOORS)


def _same_bank_trip(rng: random.Random) -> tuple[int, int]:
    source = LOW_OFFICE_FLOORS if rng.random() < 0.46 else HIGH_OFFICE_FLOORS
    floors = sorted(set(source))
    origin = rng.choice(floors)
    destination = rng.choice([floor for floor in floors if floor != origin])
    return origin, destination
