from __future__ import annotations

import unittest

from app.server import REPLAY_SCHEMA, SimulationRunner


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
        self.assertEqual("elevator-queue-lab.m3-regression-baseline.v1", baseline["schema"])
        self.assertIn("lunch", baseline["scenarios"])
        self.assertEqual(
            "candidate_improvement",
            baseline["scenarios"]["lunch"]["policies"]["capr"]["guardrail_classification"],
        )

if __name__ == "__main__":
    unittest.main()
