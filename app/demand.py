from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DemandProfile:
    name: str
    start_hour: float
    arrivals_per_minute: float


PROFILES = {
    "morning": DemandProfile("Morning rush", 8.0, 22.0),
    "lunch": DemandProfile("Lunch rush", 12.0, 16.0),
    "evening": DemandProfile("Evening rush", 18.0, 22.0),
    "normal": DemandProfile("Normal traffic", 14.0, 5.0),
    # M3 experiment scenarios use deterministic composite traces. These profiles keep the
    # simulator clock/policy context valid when those traces are replayed.
    "shock": DemandProfile("Down-peak demand shock", 17.5, 22.0),
    "mixed_day": DemandProfile("Compressed mixed office day", 8.0, 12.0),
}


# Canonical office trip-purpose mix used by every synthetic traffic regime.
# A "lobby-linked" trip has 1F as either its origin or destination. 18F is used
# as the simulator's top-floor / roof-access proxy because the physical model
# currently has 18 served levels and no separate roof transfer node.
LOBBY_FLOOR = 1
ROOFTOP_ACCESS_FLOOR = 18
LOBBY_LINKED_SHARE = 0.85
ROOFTOP_LINKED_SHARE = 0.10
INTERFLOOR_SHARE = 0.05

LOW_OFFICE_FLOORS = (2, 3, 4, 5, 6, 7, 8, 8, 9, 9)
HIGH_OFFICE_FLOORS = (10, 11, 12, 13, 14, 15, 16, 16, 17, 17)

# Within the 85% lobby-linked bucket, the time-of-day regime controls direction.
# Normal/lunch remain bidirectional, but both still visibly converge on 1F far
# more often than arbitrary floor-to-floor movement.
LOBBY_UP_PROBABILITY = {
    "morning": 0.97,
    "lunch": 0.45,
    "normal": 0.35,
    "evening": 0.03,
    "shock": 0.02,
}


def demand_contract() -> dict[str, object]:
    """Return the self-describing stochastic-demand contract for evidence artifacts."""

    return {
        "schema": "elevator-queue-lab.office-demand.v2",
        "trip_purpose_share": {
            "lobby_linked": LOBBY_LINKED_SHARE,
            "rooftop_linked": ROOFTOP_LINKED_SHARE,
            "interfloor": INTERFLOOR_SHARE,
        },
        "lobby_up_probability": dict(LOBBY_UP_PROBABILITY),
        "lobby_floor": LOBBY_FLOOR,
        "rooftop_access_floor": ROOFTOP_ACCESS_FLOOR,
        "rooftop_scope": "high-bank direct trips only",
        "transfer_model": "same-bank direct trips; no multi-leg passenger transfer",
    }


class DemandModel:
    """Synthetic office traffic with an explicit workplace trip-purpose contract.

    The default mix is 85% lobby-linked, 10% top-floor/roof-access linked and
    5% same-bank inter-floor traffic. Time-of-day scenarios change the direction
    of the lobby-linked majority rather than replacing that behavioral mix.
    """

    def __init__(self, scenario: str, seed: int = 7) -> None:
        if scenario not in PROFILES:
            raise ValueError(f"Unknown scenario: {scenario}")
        self.scenario = scenario
        self.profile = PROFILES[scenario]
        self.random = random.Random(seed)
        self.second = 0

    @property
    def start_seconds(self) -> int:
        return int(self.profile.start_hour * 3600)

    def arrivals_this_second(self) -> int:
        self.second += 1
        rate = self.profile.arrivals_per_minute / 60.0
        threshold = math.exp(-rate)
        product = 1.0
        count = 0
        while product > threshold:
            product *= self.random.random()
            count += 1
        return max(0, count - 1)

    def trip(self) -> tuple[int, int]:
        scenario = self._active_pattern()
        roll = self.random.random()
        if roll < LOBBY_LINKED_SHARE:
            return self._lobby_trip(scenario)
        if roll < LOBBY_LINKED_SHARE + ROOFTOP_LINKED_SHARE:
            return self._rooftop_trip()
        return self._same_bank_trip()

    def trip_from_hotspot(self, hotspot_floor: int) -> tuple[int, int]:
        """Generate a deterministic-purpose trip from a temporary event floor.

        Shock overlays use this to look like an actual meeting/event release
        instead of drawing extra passengers independently from every floor.
        """

        if hotspot_floor not in HIGH_OFFICE_FLOORS:
            raise ValueError("shock hotspot must be a high-bank office floor")
        roll = self.random.random()
        if roll < LOBBY_LINKED_SHARE:
            return hotspot_floor, LOBBY_FLOOR
        if roll < LOBBY_LINKED_SHARE + ROOFTOP_LINKED_SHARE:
            return hotspot_floor, ROOFTOP_ACCESS_FLOOR
        alternatives = [floor for floor in set(HIGH_OFFICE_FLOORS) if floor != hotspot_floor]
        return hotspot_floor, self.random.choice(alternatives)

    def _active_pattern(self) -> str:
        if self.scenario != "mixed_day":
            return self.scenario
        # Direct mixed-day generation is a fallback for interactive use. Research experiments
        # use the explicit composite trace in app.scenarios so segment boundaries are persisted.
        phase = (self.second // 225) % 4
        return ("morning", "lunch", "normal", "evening")[phase]

    def _office_floor(self) -> int:
        if self.random.random() < 0.46:
            return self.random.choice(LOW_OFFICE_FLOORS)
        return self.random.choice(HIGH_OFFICE_FLOORS)

    def _lobby_trip(self, scenario: str) -> tuple[int, int]:
        office_floor = self._office_floor()
        up_probability = LOBBY_UP_PROBABILITY.get(scenario, 0.35)
        if self.random.random() < up_probability:
            return LOBBY_FLOOR, office_floor
        return office_floor, LOBBY_FLOOR

    def _rooftop_trip(self) -> tuple[int, int]:
        office_floor = self.random.choice(HIGH_OFFICE_FLOORS)
        if self.random.random() < 0.5:
            return office_floor, ROOFTOP_ACCESS_FLOOR
        return ROOFTOP_ACCESS_FLOOR, office_floor

    def _same_bank_trip(self) -> tuple[int, int]:
        if self.random.random() < 0.46:
            floors = sorted(set(LOW_OFFICE_FLOORS))
        else:
            floors = sorted(set(HIGH_OFFICE_FLOORS))
        origin = self.random.choice(floors)
        destination = self.random.choice([floor for floor in floors if floor != origin])
        return origin, destination
