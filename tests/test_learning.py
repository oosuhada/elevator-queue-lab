from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.learning import (
    ACTION_COUNT,
    CAR_IDS,
    HOLD_ACTION,
    OBSERVATION_SIZE,
    DuelingDoubleDQNAgent,
    DuelingQNetwork,
    ElevatorDispatchEnv,
    Transition,
    build_decision_observation,
    evaluate_learned_policy,
    load_model_artifact,
    masked_argmax,
    save_model_artifact,
)
from app.simulator import ElevatorSimulation


ROOT = Path(__file__).resolve().parents[1]


class LearningContractTests(unittest.TestCase):
    def test_environment_is_seeded_gymnasium_compatible_and_masks_other_bank(self) -> None:
        env = ElevatorDispatchEnv(scenario="normal", seed=4, episode_seconds=45)
        state, info = env.reset(seed=4)
        self.assertEqual(OBSERVATION_SIZE, len(state))
        self.assertEqual(ACTION_COUNT, env.action_space.n)
        self.assertEqual((OBSERVATION_SIZE,), env.observation_space.shape)
        self.assertEqual(ACTION_COUNT, len(info["action_mask"]))
        call_key = info["call_key"]
        self.assertIsNotNone(call_key)
        bank = call_key[2]
        allowed_prefix = "L" if bank == "low" else "H"
        for action, car_id in enumerate(CAR_IDS):
            if not car_id.startswith(allowed_prefix):
                self.assertFalse(info["action_mask"][action])
        self.assertFalse(info["action_mask"][HOLD_ACTION])

        second = ElevatorDispatchEnv(scenario="normal", seed=4, episode_seconds=45)
        second_state, second_info = second.reset(seed=4)
        self.assertEqual(state, second_state)
        self.assertEqual(info["action_mask"], second_info["action_mask"])
        self.assertEqual(info["trace_digest"], second_info["trace_digest"])

    def test_environment_rejects_masked_action_and_preserves_simulator_audit(self) -> None:
        env = ElevatorDispatchEnv(scenario="morning", seed=2, episode_seconds=40)
        state, info = env.reset(seed=2)
        del state
        masked = next(index for index, allowed in enumerate(info["action_mask"]) if not allowed)
        with self.assertRaises(ValueError):
            env.step(masked)
        action = next(index for index, allowed in enumerate(info["action_mask"]) if allowed)
        _, _, _, _, next_info = env.step(action)
        self.assertTrue(next_info["audit"]["ok"])

    def test_feature_ablation_zeros_only_declared_group(self) -> None:
        env = ElevatorDispatchEnv(scenario="lunch", seed=3, episode_seconds=60)
        _, _ = env.reset(seed=3)
        self.assertIsNotNone(env.simulation)
        self.assertIsNotNone(env.current_key)
        simulation = env.simulation
        key = env.current_key
        call = simulation.hall_calls[key]
        base = build_decision_observation(
            call,
            simulation.compatible_candidates(key),
            simulation.config,
            queue_size=simulation.call_queue_size(key),
            now=simulation.sim_time,
            scenario="lunch",
        )
        ablated = build_decision_observation(
            call,
            simulation.compatible_candidates(key),
            simulation.config,
            queue_size=simulation.call_queue_size(key),
            now=simulation.sim_time,
            scenario="lunch",
            ablations=("capacity",),
        )
        self.assertEqual(base.action_mask, ablated.action_mask)
        for index in base.feature_groups["capacity"]:
            self.assertEqual(0.0, ablated.values[index])
        untouched = set(range(OBSERVATION_SIZE)) - set(base.feature_groups["capacity"])
        self.assertTrue(any(base.values[index] == ablated.values[index] for index in untouched))

    def test_dueling_network_trains_and_round_trips_model_artifact(self) -> None:
        network = DuelingQNetwork(seed=9, hidden_size=8)
        state = tuple(0.1 if index % 2 else -0.1 for index in range(OBSERVATION_SIZE))
        before = network.q_values(state)
        network.train_one(state, action=1, target=2.0, learning_rate=0.01)
        after = network.q_values(state)
        self.assertNotEqual(before, after)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            save_model_artifact(path, network, metadata={"test": True})
            restored, metadata = load_model_artifact(path)
            self.assertEqual(metadata, {"test": True})
            for actual, expected in zip(restored.q_values(state), network.q_values(state)):
                self.assertAlmostEqual(actual, expected, places=12)

    def test_double_dqn_agent_uses_masked_actions_and_updates(self) -> None:
        agent = DuelingDoubleDQNAgent(seed=11, hidden_size=8, batch_size=2, train_frequency=1)
        state = tuple(0.01 * (index % 5) for index in range(OBSERVATION_SIZE))
        mask = (True, False, True, False, False, False, False)
        self.assertIn(agent.act(state, mask, epsilon=0.0), (0, 2))
        transition = Transition(state, 0, -1.0, state, mask, False)
        self.assertIsNone(agent.observe(transition))
        loss = agent.observe(transition)
        self.assertIsNotNone(loss)
        self.assertEqual(1, agent.gradient_steps)
        self.assertEqual(0, masked_argmax([3, 100, 2, 100, 100, 100, 100], mask))

    def test_learned_evaluation_uses_common_trace_for_all_policies(self) -> None:
        network = DuelingQNetwork(seed=13, hidden_size=8)
        evidence = evaluate_learned_policy(
            network,
            scenarios=("normal",),
            seeds=(21, 22),
            seconds=45,
        )
        runs = evidence["raw_runs"]
        self.assertEqual(6, len(runs))
        for seed in (21, 22):
            digests = {
                row["trace_digest"]
                for row in runs
                if row["seed"] == seed
            }
            self.assertEqual(1, len(digests))
        self.assertEqual(
            {"collective", "capr", "rl"},
            {row["policy"] for row in runs},
        )

    def test_checked_in_model_runs_as_real_simulator_policy(self) -> None:
        model_path = ROOT / "models" / "m5-ddqn-baseline.json"
        network, metadata = load_model_artifact(model_path)
        self.assertEqual(OBSERVATION_SIZE, network.input_size)
        self.assertEqual([1, 2, 3, 4, 5, 6], metadata["training_passenger_seeds"])
        self.assertEqual([21, 22, 23, 24, 25, 26, 27, 28, 29, 30], metadata["held_out_passenger_seeds"])

        simulation = ElevatorSimulation(
            scenario="mixed_day",
            policy_name="rl",
            seed=21,
        )
        simulation.run(60)
        self.assertEqual("rl", simulation.policy_name)
        self.assertTrue(simulation.audit()["ok"])

    def test_checked_in_evidence_keeps_training_and_held_out_contract_disjoint(self) -> None:
        payload = json.loads(
            (ROOT / "evidence" / "m5-heldout-evaluation.json").read_text(encoding="utf-8")
        )
        training = payload["training_contract"]
        held_out = payload["held_out_contract"]
        self.assertTrue(held_out["disjoint_from_training"])
        self.assertTrue(
            set(training["passenger_seeds"]).isdisjoint(held_out["passenger_seeds"])
        )
        self.assertNotIn("mixed_day", training["scenarios"])
        self.assertIn("mixed_day", held_out["scenarios"])
        self.assertFalse(payload["verdict"]["accepted_as_general_improvement"])
        self.assertEqual(
            ["mixed_day"],
            payload["verdict"]["candidate_improvement_scenarios"],
        )


if __name__ == "__main__":
    unittest.main()
