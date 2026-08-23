from __future__ import annotations

import unittest

from app.artifacts import build_artifact_catalog, build_run_artifact, build_trace_manifest
from app.simulator import ElevatorSimulation
from app.workbench import answer_run_question, build_decision_graph, build_objects, build_models_payload


class WorkbenchContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.simulation = ElevatorSimulation("evening", "capr", seed=42)
        self.simulation.step(180)
        self.run_id = "run-test-contract"

    def test_run_artifact_preserves_seed_config_and_trace_identity(self) -> None:
        manifest = build_trace_manifest(self.simulation)
        artifact = build_run_artifact(self.simulation, self.run_id)

        self.assertEqual(artifact["schema_version"], "elevator-queue-lab.run.v1")
        self.assertEqual(artifact["run_id"], self.run_id)
        self.assertEqual(artifact["seed"], 42)
        self.assertEqual(artifact["scenario"], "evening")
        self.assertEqual(artifact["policy"], "capr")
        self.assertEqual(artifact["provenance"]["trace_identity_sha256"], manifest["identity_sha256"])
        self.assertEqual(manifest["building_configuration"]["floors"], 18)
        self.assertEqual(manifest["building_configuration"]["elevators_per_bank"], 3)

    def test_object_projection_exposes_required_research_objects(self) -> None:
        payload = build_objects(self.simulation, self.run_id)

        for object_type in (
            "Elevator",
            "Passenger",
            "HallCall",
            "DispatchDecision",
            "SimulationRun",
            "Scenario",
            "Policy",
            "Experiment",
            "Model",
            "Evidence",
            "TheoryEvidence",
        ):
            self.assertIn(object_type, payload["object_types"])
            self.assertIn(object_type, payload["counts"])
        self.assertEqual(payload["counts"]["Elevator"], 6)
        self.assertGreater(payload["counts"]["Passenger"], 0)
        self.assertGreater(payload["counts"]["DispatchDecision"], 0)

    def test_decision_graph_is_a_read_only_projection_with_valid_edges(self) -> None:
        graph = build_decision_graph(self.simulation, self.run_id)
        node_ids = {node["id"] for node in graph["nodes"]}
        node_types = {node["type"] for node in graph["nodes"]}
        relations = {edge["relation"] for edge in graph["edges"]}

        self.assertEqual(graph["provenance"]["database"], None)
        self.assertEqual(graph["provenance"]["projection"], "read_only")
        self.assertGreater(len(node_ids), 6)
        self.assertTrue({"HallCall", "DispatchDecision", "Elevator", "Pickup", "WaitMetric"}.issubset(node_types))
        self.assertTrue({"evaluated_by", "selected", "produced", "contributed_to"}.issubset(relations))
        for edge in graph["edges"]:
            self.assertIn(edge["source"], node_ids)
            self.assertIn(edge["target"], node_ids)

    def test_ask_run_uses_deterministic_evidence_without_llm(self) -> None:
        comparison = answer_run_question(
            self.simulation,
            self.run_id,
            "Compare this run with collective",
        )
        decision = answer_run_question(
            self.simulation,
            self.run_id,
            "Why did CAPR choose this elevator?",
        )

        self.assertEqual(comparison["intent"], "policy_comparison")
        self.assertFalse(comparison["llm_required"])
        self.assertEqual(comparison["expression_layer"], "deterministic")
        self.assertTrue(comparison["evidence"])
        self.assertEqual(decision["intent"], "latest_dispatch_explanation")
        self.assertTrue(decision["evidence"])

    def test_artifact_catalog_and_model_payload_point_to_committed_sources(self) -> None:
        catalog = build_artifact_catalog(self.simulation, self.run_id)
        models = build_models_payload()

        artifact_types = {artifact["artifact_type"] for artifact in catalog["artifacts"]}
        self.assertIn("SimulationRunArtifact", artifact_types)
        self.assertIn("PassengerTraceArtifact", artifact_types)
        self.assertIn("DispatchDecisionArtifact", artifact_types)
        self.assertIn("ExperimentArtifact", artifact_types)
        self.assertIn("PolicyEvaluationArtifact", artifact_types)
        self.assertIn("ModelArtifact", artifact_types)
        self.assertIn("TheoryEvidenceArtifact", artifact_types)
        required_provenance = {
            "schema_version",
            "artifact_version",
            "simulator_version",
            "source",
            "seed",
            "scenario",
            "policy",
            "config",
            "created_at",
            "trace_sha256",
            "evidence_source",
        }
        for artifact in catalog["artifacts"]:
            self.assertTrue(required_provenance.issubset(artifact["provenance"]))
        self.assertEqual(models["source"]["model"], "models/m5-ddqn-baseline.json")
        self.assertIn("verdict", models["evaluation"])


if __name__ == "__main__":
    unittest.main()
