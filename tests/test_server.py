from __future__ import annotations

import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from app.server import Handler, REPLAY_SCHEMA, SimulationRunner


class ServerRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = SimulationRunner()
        self.runner.running = False

    def tearDown(self) -> None:
        self.runner.closed.set()
        self.runner.thread.join(timeout=1)

    def test_replay_buffer_records_exact_step_state_and_survives_save(self) -> None:
        initial = self.runner.replay()
        self.assertEqual(REPLAY_SCHEMA, initial["schema"])
        self.assertGreaterEqual(initial["frame_count"], 1)

        snapshot = self.runner.control({"action": "step"})
        replay = self.runner.replay()
        self.assertEqual(snapshot["sim_time"], replay["frames"][-1]["sim_time"])
        self.assertEqual(snapshot["clock"], replay["frames"][-1]["clock"])
        self.assertEqual(snapshot["metrics"]["current_queue"], replay["frames"][-1]["metrics"]["current_queue"])

        saved = self.runner.replay_control({"action": "save"})
        self.assertEqual("saved_run", saved["source"])
        saved_count = saved["frame_count"]
        self.runner.control({"action": "reset", "scenario": "evening"})
        after_reset = self.runner.replay()
        self.assertEqual("saved_run", after_reset["source"])
        self.assertEqual(saved_count, after_reset["frame_count"])

    def test_replay_frames_are_compact_and_include_inspection_state(self) -> None:
        frame = self.runner.replay()["frames"][-1]
        self.assertEqual(
            {
                "scenario",
                "policy",
                "sim_time",
                "clock",
                "metrics",
                "elevators",
                "queues",
                "calls",
                "event_tail",
                "decision_tail",
                "simulation_config",
            },
            set(frame),
        )
        self.assertNotIn("history", frame)
        self.assertNotIn("audit", frame)

    def test_experiment_api_is_backed_by_checked_in_m3_baseline(self) -> None:
        payload = self.runner.experiment()
        self.assertEqual("elevator-queue-lab.experiment-ui.v1", payload["schema"])
        baseline = payload["baseline"]
        self.assertEqual("elevator-queue-lab.m3-regression-baseline.v2", baseline["schema"])
        self.assertIn("lunch", baseline["scenarios"])
        lunch_capr = baseline["scenarios"]["lunch"]["policies"]["capr"]
        self.assertEqual(30, len(lunch_capr["avg_wait_seed_values"]))
        self.assertGreater(lunch_capr["avg_wait_ci95_halfwidth"], 0)
        self.assertIn("p99_wait", lunch_capr)
        self.assertIn("worst_floor_mean_wait", lunch_capr)
        self.assertEqual(
            "candidate_improvement",
            lunch_capr["guardrail_classification"],
        )

    def test_theory_api_exposes_discovery_and_held_out_validation(self) -> None:
        payload = self.runner.theory()
        self.assertEqual("elevator-queue-lab.theory-ui.v1", payload["schema"])
        discovery = payload["discovery"]
        validation = payload["validation"]
        self.assertEqual("elevator-queue-lab.m7-bidirectional-load-theory.v1", discovery["schema"])
        self.assertEqual("elevator-queue-lab.m7-threshold-validation.v1", validation["schema"])
        self.assertEqual(40, len(discovery["cells"]))
        self.assertEqual(18, len(validation["cells"]))
        self.assertAlmostEqual(12.33, discovery["theory"]["best_single_threshold"]["threshold"], places=2)
        self.assertTrue(validation["method"]["grid_was_not_used_to_fit_threshold"])

    def test_static_assets_disable_intermediary_caching(self) -> None:
        handler = type("TestElevatorQueueHandler", (Handler,), {"runner": self.runner})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}"
            for path in ("/", "/app.js", "/styles.css"):
                with urllib.request.urlopen(base_url + path) as response:
                    self.assertEqual("no-store", response.headers.get("Cache-Control"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

if __name__ == "__main__":
    unittest.main()
