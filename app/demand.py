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
}


class DemandModel:
    """Synthetic office traffic with intentionally legible rush-hour assumptions."""

    def __init__(self, scenario: str, seed: int = 7) -> None:
        if scenario not in PROFILES:
            raise ValueError(f"Unknown scenario: {scenario}")
        self.scenario = scenario
        self.profile = PROFILES[scenario]
        self.random = random.Random(seed)

    @property
    def start_seconds(self) -> int:
        return int(self.profile.start_hour * 3600)

    def arrivals_this_second(self) -> int:
        rate = self.profile.arrivals_per_minute / 60.0
        # Poisson sample without numpy; lambda is below 1 for the current profiles.
        threshold = math.exp(-rate)
        product = 1.0
        count = 0
        while product > threshold:
            product *= self.random.random()
            count += 1
        return max(0, count - 1)

    def trip(self) -> tuple[int, int]:
        if self.scenario == "morning":
            # Office workers enter through the lobby. A small amount of internal traffic
            # prevents the benchmark from becoming a one-direction toy problem.
            if self.random.random() < 0.88:
                return 1, self._office_floor()
            return self._same_bank_trip()

        if self.scenario == "evening":
            if self.random.random() < 0.88:
                return self._office_floor(), 1
            return self._same_bank_trip()

        if self.scenario == "lunch":
            roll = self.random.random()
            if roll < 0.48:
                return self._office_floor(), 1
            if roll < 0.88:
                return 1, self._office_floor()
            return self._same_bank_trip()

        roll = self.random.random()
        if roll < 0.42:
            return 1, self._office_floor()
        if roll < 0.84:
            return self._office_floor(), 1
        return self._same_bank_trip()

    def _office_floor(self) -> int:
        # Slightly bias the top floors of each bank to create visible hotspots.
        low = [2, 3, 4, 5, 6, 7, 8, 8, 9, 9]
        high = [10, 11, 12, 13, 14, 15, 16, 16, 17, 17, 18]
        if self.random.random() < 0.46:
            return self.random.choice(low)
        return self.random.choice(high)

    def _same_bank_trip(self) -> tuple[int, int]:
        if self.random.random() < 0.46:
            floors = list(range(2, 10))
        else:
            floors = list(range(10, 19))
        origin = self.random.choice(floors)
        destination = self.random.choice([floor for floor in floors if floor != origin])
        return origin, destination

