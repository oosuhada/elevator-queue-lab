from __future__ import annotations

import unittest

from app.domain import SimulationConfig
from app.physics import MotionProfile, service_dwell_seconds
from app.simulator import ElevatorSimulation
from app.trace import DemandEvent, PassengerTrace, generate_trace


class SimulationTests(unittest.TestCase):
    def test_motion_profile_is_symmetric_and_reaches_target(self) -> None:
        profile = MotionProfile.build(distance_m=36.0, max_speed_mps=2.5, acceleration_mps2=1.0)
        self.assertGreater(profile.duration_s, 0)
        self.assertAlmostEqual(0.0, profile.distance_at(0.0))
        self.assertAlmostEqual(36.0, profile.distance_at(profile.duration_s))
        halfway = profile.distance_at(profile.duration_s / 2)
        self.assertAlmostEqual(18.0, halfway, places=6)

    def test_longer_slow_car_trip_takes_longer(self) -> None:
        fast = MotionProfile.build(36.0, 2.5, 1.0)
        slow = MotionProfile.build(36.0, 1.5, 1.0)
        self.assertGreater(slow.duration_s, fast.duration_s)

    def test_passenger_transfer_count_extends_door_dwell(self) -> None:
        one = service_dwell_seconds(1, 1.5, 0.45)
        six = service_dwell_seconds(6, 1.5, 0.45)
        self.assertAlmostEqual(1.95, one)
        self.assertGreater(six, one)

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

    def test_subsecond_physics_preserves_invariants_across_100_seeds(self) -> None:
        config = SimulationConfig(time_step_seconds=0.25)
        for seed in range(1, 101):
            simulation = ElevatorSimulation("normal", "collective", seed=seed, config=config)
            simulation.run(60)
            audit = simulation.audit()
            self.assertTrue(audit["ok"], f"seed={seed}: {audit}")
            for car in simulation.elevators:
                self.assertGreaterEqual(car.floor, 1.0)
                self.assertLessEqual(car.floor, config.floors)
                self.assertLessEqual(len(car.onboard), car.capacity)

    def test_optional_passenger_patience_records_abandonment(self) -> None:
        trace = PassengerTrace(
            scenario="normal",
            seed=1,
            duration_seconds=3,
            events=(DemandEvent(at=1, passenger_id=1, origin=18, destination=10),),
        )
        config = SimulationConfig(passenger_patience_seconds=0.1)
        simulation = ElevatorSimulation("normal", "collective", trace=trace, config=config)
        simulation.run(2)
        audit = simulation.audit()
        self.assertTrue(audit["ok"], audit)
        self.assertEqual(1, audit["abandoned"])
        self.assertEqual(1, audit["event_counts"]["abandon"])

    def test_rush_hour_produces_passenger_metrics(self) -> None:
        metrics = ElevatorSimulation("morning", "collective", seed=9).run(300)
        self.assertGreater(metrics["arrivals"], 0)
        self.assertGreater(metrics["served"], 0)
        self.assertGreaterEqual(metrics["avg_wait"], 0)
        self.assertGreaterEqual(metrics["p95_wait"], 0)


if __name__ == "__main__":
    unittest.main()

