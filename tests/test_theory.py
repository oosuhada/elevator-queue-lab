from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.policies import CAPRPolicy, CAPRStaticPolicy, build_policy
from app.theory import ParametricOfficeDemand, generate_parametric_trace


class TheoryExperimentTests(unittest.TestCase):
    def test_directional_mixing_and_bidirectional_load_rate(self) -> None:
        one_way = ParametricOfficeDemand(20.0, 0.0)
        balanced = ParametricOfficeDemand(20.0, 0.5)
        mirrored = ParametricOfficeDemand(20.0, 0.8)
        mirrored_other = ParametricOfficeDemand(20.0, 0.2)

        self.assertEqual(0.0, one_way.directional_mixing_index)
        self.assertEqual(1.0, balanced.directional_mixing_index)
        self.assertEqual(20.0, balanced.bidirectional_load_rate)
        self.assertAlmostEqual(mirrored.directional_mixing_index, mirrored_other.directional_mixing_index)

    def test_parametric_trace_is_deterministic_and_preserves_office_trip_constraints(self) -> None:
        spec = ParametricOfficeDemand(16.0, 0.45)
        first = generate_parametric_trace(spec, 180, 17)
        second = generate_parametric_trace(spec, 180, 17)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.events, second.events)
        self.assertTrue(first.events)
        for event in first.events:
            self.assertNotEqual(event.origin, event.destination)
            self.assertTrue(
                1 in {event.origin, event.destination}
                or 18 in {event.origin, event.destination}
                or (2 <= event.origin <= 9 and 2 <= event.destination <= 9)
                or (10 <= event.origin <= 17 and 10 <= event.destination <= 17)
            )

    def test_capr_static_is_exact_continuous_reassignment_ablation(self) -> None:
        capr = build_policy("capr")
        static = build_policy("capr_static")
        self.assertTrue(capr.continuous_reassignment)
        self.assertFalse(static.continuous_reassignment)
        self.assertIs(CAPRStaticPolicy.parking_floor, CAPRPolicy.parking_floor)
        self.assertIs(CAPRStaticPolicy.decide, CAPRPolicy.decide)
        self.assertEqual("capr_static", static.name)

    def test_checked_in_m7_evidence_preserves_discovery_validation_separation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        discovery = json.loads((root / "evidence/m7-bidirectional-load-sweep.json").read_text())
        validation = json.loads((root / "evidence/m7-threshold-validation.json").read_text())
        self.assertEqual(40, len(discovery["cells"]))
        self.assertEqual(18, len(validation["cells"]))
        discovery_intensity = set(discovery["method"]["intensity_grid"])
        validation_intensity = set(validation["method"]["intensity_grid"])
        discovery_direction = set(discovery["method"]["lobby_up_probability_grid"])
        validation_direction = set(validation["method"]["lobby_up_probability_grid"])
        self.assertFalse(discovery_intensity & validation_intensity)
        self.assertFalse(discovery_direction & validation_direction)
        fitted = discovery["theory"]["best_single_threshold"]
        frozen = validation["frozen_discovery_threshold"]
        self.assertEqual(fitted["threshold"], frozen["threshold"])
        self.assertEqual(fitted["direction"], frozen["direction"])
        self.assertTrue(validation["method"]["grid_was_not_used_to_fit_threshold"])
        self.assertEqual(1.0, validation["result"]["recall"])
        self.assertTrue(validation["result"]["all_threshold_positive_cells_have_negative_mean_delta"])
        self.assertGreater(
            validation["result"]["frozen_linear_effect_model"]["correlation_observed_vs_predicted"],
            0.6,
        )
        self.assertLess(validation["result"]["frozen_linear_effect_model"]["mae_seconds"], 1.0)
        gated = validation["result"]["gated_policy_projection"]
        self.assertGreater(gated["wait_gain_retained_vs_always_on_capr"], 0.85)
        self.assertGreater(gated["energy_overhead_reduction_vs_always_on_capr"], 0.5)


if __name__ == "__main__":
    unittest.main()
