from __future__ import annotations

import json
import unittest

from app.analytics import analyze_simulation, paired_cohens_dz, percentile
from app.scenarios import SCENARIOS, generate_scenario_trace
from app.simulator import ElevatorSimulation
from scripts.run_experiment import POLICIES, measurement_window, run_experiment


class ExperimentTests(unittest.TestCase):
    def test_percentile_interpolates_and_effect_size_stays_finite(self) -> None:
        self.assertEqual(2.5, percentile([1, 2, 3, 4], 0.5))
        self.assertEqual(0.0, paired_cohens_dz([0.0, 0.0, 0.0]))
        self.assertEqual(20.0, paired_cohens_dz([2.0, 2.0, 2.0]))

    def test_scenario_matrix_contains_required_regimes(self) -> None:
        self.assertEqual(
            ("morning", "lunch", "normal", "evening", "shock", "mixed_day"),
            SCENARIOS,
        )

    def test_shock_trace_is_deterministic_and_adds_evening_burst(self) -> None:
        first = generate_scenario_trace("shock", 180, 7)
        second = generate_scenario_trace("shock", 180, 7)
        evening = generate_scenario_trace("evening", 180, 7)
        self.assertEqual(first.digest, second.digest)
        self.assertGreater(len(first.events), len(evening.events))
        self.assertEqual("shock", first.scenario)

    def test_mixed_day_trace_is_deterministic_and_spans_run(self) -> None:
        trace = generate_scenario_trace("mixed_day", 181, 3)
        self.assertEqual(trace.digest, generate_scenario_trace("mixed_day", 181, 3).digest)
        self.assertEqual(181, trace.duration_seconds)
        self.assertTrue(all(1 <= event.at <= 181 for event in trace.events))
        self.assertEqual(list(range(1, len(trace.events) + 1)), [event.passenger_id for event in trace.events])

    def test_ledger_analytics_exposes_tail_fairness_energy_and_reassignment_latency(self) -> None:
        trace = generate_scenario_trace("evening", 120, 4)
        simulation = ElevatorSimulation("evening", "collective", seed=4, trace=trace)
        simulation.run(120)
        metrics = analyze_simulation(simulation)
        for key in (
            "p50_wait",
            "p95_wait",
            "p99_wait",
            "avg_journey",
            "worst_floor_mean_wait",
            "floor_wait_std",
            "energy_proxy",
            "distance_m",
            "unfinished",
            "avg_reassignment_latency",
            "p95_reassignment_latency",
        ):
            self.assertIn(key, metrics)
        self.assertGreaterEqual(float(metrics["energy_proxy"]), float(metrics["distance_m"]))

        synthetic = ElevatorSimulation("normal", "capr", seed=1)
        synthetic.ledger.record(
            1.0,
            "assign",
            elevator_id="H1",
            floor=16,
            bank="high",
            details={"direction": -1, "destination": None},
        )
        synthetic.ledger.record(
            4.5,
            "reassign",
            elevator_id="H2",
            floor=16,
            bank="high",
            details={"direction": -1, "destination": None, "previous_elevator": "H1"},
        )
        latency = analyze_simulation(synthetic)
        self.assertEqual(3.5, latency["avg_reassignment_latency"])
        self.assertEqual(3.5, latency["p95_reassignment_latency"])

    def test_measurement_window_is_explicit_and_propagated_to_runs(self) -> None:
        expected = {
            "warmup_seconds": 0,
            "measurement_start_seconds": 0,
            "measurement_seconds": 30,
            "measurement_end_seconds": 30,
        }
        self.assertEqual(expected, measurement_window(30))
        payload = run_experiment("normal", 30, 1)
        self.assertEqual(
            {"lobby_linked": 0.85, "rooftop_linked": 0.10, "interfloor": 0.05},
            payload["demand_contract"]["trip_purpose_share"],
        )
        self.assertEqual(expected, payload["measurement_window"])
        scenario = payload["scenario_matrix"][0]
        self.assertEqual(expected, scenario["measurement_window"])
        for row in scenario["raw_runs"]:
            for key, value in expected.items():
                self.assertEqual(value, row[key])

    def test_experiment_uses_identical_trace_per_seed_across_policies(self) -> None:
        payload = run_experiment("shock", 90, 3)
        scenario = payload["scenario_matrix"][0]
        self.assertEqual(len(POLICIES) * 3, len(scenario["raw_runs"]))
        by_seed: dict[int, set[str]] = {}
        for row in scenario["raw_runs"]:
            by_seed.setdefault(int(row["seed"]), set()).add(str(row["trace_digest"]))
        self.assertTrue(all(len(digests) == 1 for digests in by_seed.values()))
        self.assertEqual(set(POLICIES), {item["policy"] for item in scenario["policies"]})
        rendered = json.dumps(payload, allow_nan=False)
        self.assertIn("paired_vs_collective", rendered)
        self.assertIn("guardrail_classification", rendered)
        self.assertIn("reassignment_latency", rendered)


if __name__ == "__main__":
    unittest.main()
