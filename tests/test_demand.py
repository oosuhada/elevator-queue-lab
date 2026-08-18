from __future__ import annotations

import unittest

from app.demand import (
    INTERFLOOR_SHARE,
    LOBBY_FLOOR,
    LOBBY_LINKED_SHARE,
    ROOFTOP_ACCESS_FLOOR,
    ROOFTOP_LINKED_SHARE,
    DemandModel,
)
from app.scenarios import generate_scenario_trace


def trip_purpose(origin: int, destination: int) -> str:
    if LOBBY_FLOOR in {origin, destination}:
        return "lobby"
    if ROOFTOP_ACCESS_FLOOR in {origin, destination}:
        return "rooftop"
    return "interfloor"


class DemandBehaviorTests(unittest.TestCase):
    def test_trip_purpose_mix_matches_office_contract(self) -> None:
        demand = DemandModel("normal", seed=2026)
        counts = {"lobby": 0, "rooftop": 0, "interfloor": 0}
        samples = 100_000
        for _ in range(samples):
            origin, destination = demand.trip()
            counts[trip_purpose(origin, destination)] += 1

        self.assertAlmostEqual(LOBBY_LINKED_SHARE, counts["lobby"] / samples, delta=0.006)
        self.assertAlmostEqual(ROOFTOP_LINKED_SHARE, counts["rooftop"] / samples, delta=0.004)
        self.assertAlmostEqual(INTERFLOOR_SHARE, counts["interfloor"] / samples, delta=0.003)

    def test_lobby_majority_changes_direction_by_regime(self) -> None:
        for scenario, expected_up in (("morning", 0.97), ("normal", 0.35), ("evening", 0.03)):
            demand = DemandModel(scenario, seed=17)
            lobby = []
            for _ in range(30_000):
                origin, destination = demand.trip()
                if trip_purpose(origin, destination) == "lobby":
                    lobby.append(origin == LOBBY_FLOOR)
            actual_up = sum(lobby) / len(lobby)
            self.assertAlmostEqual(expected_up, actual_up, delta=0.015, msg=scenario)

    def test_rooftop_and_interfloor_trips_remain_bank_feasible(self) -> None:
        demand = DemandModel("normal", seed=23)
        for _ in range(50_000):
            origin, destination = demand.trip()
            purpose = trip_purpose(origin, destination)
            if purpose == "rooftop":
                other = destination if origin == ROOFTOP_ACCESS_FLOOR else origin
                self.assertGreaterEqual(other, 10)
                self.assertLessEqual(other, 17)
            elif purpose == "interfloor":
                self.assertTrue(
                    (2 <= origin <= 9 and 2 <= destination <= 9)
                    or (10 <= origin <= 17 and 10 <= destination <= 17)
                )

    def test_shock_extra_stream_is_a_real_floor_hotspot(self) -> None:
        shock = generate_scenario_trace("shock", 240, seed=9)
        evening = generate_scenario_trace("evening", 240, seed=9)
        shock_pairs = [(event.at, event.origin, event.destination) for event in shock.events]
        evening_pairs = {(event.at, event.origin, event.destination) for event in evening.events}
        extras = [pair for pair in shock_pairs if pair not in evening_pairs]
        self.assertTrue(extras)
        self.assertTrue(all(origin == 16 for _, origin, _ in extras))


if __name__ == "__main__":
    unittest.main()
