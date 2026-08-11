from __future__ import annotations

import unittest

from app.simulator import ElevatorSimulation


class SimulationTests(unittest.TestCase):
    def test_six_cars_are_split_into_two_banks(self) -> None:
        simulation = ElevatorSimulation(seed=1)
        self.assertEqual(6, len(simulation.elevators))
        self.assertEqual(3, sum(car.bank == "low" for car in simulation.elevators))
        self.assertEqual(3, sum(car.bank == "high" for car in simulation.elevators))

    def test_bank_trip_constraints(self) -> None:
        simulation = ElevatorSimulation(seed=1)
        low = next(car for car in simulation.elevators if car.bank == "low")
        high = next(car for car in simulation.elevators if car.bank == "high")
        self.assertTrue(low.can_serve_trip(1, 8))
        self.assertFalse(low.can_serve_trip(1, 16))
        self.assertTrue(high.can_serve_trip(1, 16))
        self.assertFalse(high.can_serve_trip(1, 8))

    def test_seeded_run_is_deterministic(self) -> None:
        first = ElevatorSimulation("evening", "queue_aware", seed=42).run(300)
        second = ElevatorSimulation("evening", "queue_aware", seed=42).run(300)
        self.assertEqual(first, second)

    def test_rush_hour_produces_passenger_metrics(self) -> None:
        metrics = ElevatorSimulation("morning", "collective", seed=9).run(300)
        self.assertGreater(metrics["arrivals"], 0)
        self.assertGreater(metrics["served"], 0)
        self.assertGreaterEqual(metrics["avg_wait"], 0)
        self.assertGreaterEqual(metrics["p95_wait"], 0)


if __name__ == "__main__":
    unittest.main()

