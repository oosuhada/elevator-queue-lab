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


class DemandModel:
    """Synthetic office traffic with intentionally legible rush-hour assumptions."""

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
        if scenario == "morning":
            if self.random.random() < 0.88:
                return 1, self._office_floor()
            return self._same_bank_trip()

        if scenario in {"evening", "shock"}:
            if self.random.random() < 0.88:
                return self._office_floor(), 1
            return self._same_bank_trip()

        if scenario == "lunch":
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

    def _active_pattern(self) -> str:
        if self.scenario != "mixed_day":
            return self.scenario
        # Direct mixed-day generation is a fallback for interactive use. Research experiments
        # use the explicit composite trace in app.scenarios so segment boundaries are persisted.
        phase = (self.second // 225) % 4
        return ("morning", "lunch", "normal", "evening")[phase]

    def _office_floor(self) -> int:
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
