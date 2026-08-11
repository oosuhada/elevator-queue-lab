from __future__ import annotations

import unittest

from app.simulator import ElevatorSimulation
from app.trace import PassengerTrace, generate_trace


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

    def test_passenger_trace_is_byte_deterministic_and_round_trips(self) -> None:
        first = generate_trace("evening", 300, seed=42)
        second = generate_trace("evening", 300, seed=42)
        self.assertEqual(first.to_json().encode("utf-8"), second.to_json().encode("utf-8"))
        self.assertEqual(first.digest, second.digest)
        restored = PassengerTrace.from_json(first.to_json())
        self.assertEqual(first, restored)

    def test_trace_driven_run_reconciles_passenger_lifecycle_and_events(self) -> None:
        trace = generate_trace("morning", 300, seed=17)
        simulation = ElevatorSimulation("morning", "collective", seed=999, trace=trace)
        simulation.run(300)
        audit = simulation.audit()
        self.assertTrue(audit["ok"], audit)
        self.assertEqual(len(trace.events), audit["arrivals"])
        self.assertEqual(audit["arrivals"], audit["event_counts"]["arrival"])

    def test_rush_hour_produces_passenger_metrics(self) -> None:
        metrics = ElevatorSimulation("morning", "collective", seed=9).run(300)
        self.assertGreater(metrics["arrivals"], 0)
        self.assertGreater(metrics["served"], 0)
        self.assertGreaterEqual(metrics["avg_wait"], 0)
        self.assertGreaterEqual(metrics["p95_wait"], 0)


if __name__ == "__main__":
    unittest.main()

