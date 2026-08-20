from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

try:  # Gymnasium is optional; CI and the portable baseline require only the stdlib.
    import gymnasium as gym  # type: ignore
    from gymnasium import spaces  # type: ignore

    GymEnvBase = gym.Env
except ImportError:  # pragma: no cover - exercised indirectly in the dependency-free CI image.
    class GymEnvBase:  # type: ignore[no-redef]
        metadata: dict[str, object] = {}

    class _Discrete:
        def __init__(self, n: int) -> None:
            self.n = n

        def contains(self, value: object) -> bool:
            return isinstance(value, int) and 0 <= value < self.n

    class _Box:
        def __init__(self, low: float, high: float, shape: tuple[int, ...]) -> None:
            self.low = low
            self.high = high
            self.shape = shape

    class _Spaces:
        Discrete = _Discrete
        Box = _Box

    spaces = _Spaces()  # type: ignore[assignment]

from .analytics import analyze_simulation, guardrail_classification, paired_comparison, summarize_metric
from .dispatch import CandidateEvaluation, DispatchDecision, build_evaluation
from .domain import Elevator, HallCall, SimulationConfig
from .scenarios import generate_scenario_trace
from .simulator import CallKey, ElevatorSimulation


CAR_IDS = ("L1", "L2", "L3", "H1", "H2", "H3")
HOLD_ACTION = len(CAR_IDS)
ACTION_COUNT = len(CAR_IDS) + 1
SCENARIOS = ("morning", "lunch", "normal", "evening", "shock", "mixed_day")


def parking_hotspot(scenario: str, bank: str, elevator_id: str) -> int:
    if scenario == "morning":
        return 1
    if scenario == "lunch":
        if elevator_id.endswith("1"):
            return 1
        return 6 if bank == "low" else 14
    if scenario == "evening":
        return 8 if bank == "low" else 16
    return 5 if bank == "low" else 14


@dataclass(frozen=True, slots=True)
class RewardWeights:
    mean_wait: float = 0.06
    tail_wait: float = 0.04
    floor_gap: float = 0.03
    capacity_miss: float = 2.5
    energy: float = 0.004
    served: float = 0.30


@dataclass(frozen=True, slots=True)
class DecisionObservation:
    values: tuple[float, ...]
    action_mask: tuple[bool, ...]
    evaluations: tuple[CandidateEvaluation, ...]
    feature_groups: dict[str, tuple[int, ...]]


def _phase_code(elevator: Elevator) -> float:
    if elevator.phase == "moving":
        return 1.0
    if elevator.phase.startswith("door_"):
        return 0.5
    return 0.0


def build_decision_observation(
    call: HallCall,
    elevators: Iterable[Elevator],
    config: SimulationConfig,
    *,
    queue_size: int,
    now: float,
    scenario: str,
    ablations: Iterable[str] = (),
) -> DecisionObservation:
    """Create the canonical fixed-length M5 state and infeasible-action mask.

    The same function is used by the training environment and the deployed learned policy.
    Missing/incompatible cars occupy zero-filled slots, which keeps the action/state contract
    stable across low/high banks without leaking an impossible action into the mask.
    """

    cars = list(elevators)
    evaluations = tuple(
        build_evaluation(
            elevator,
            call,
            config,
            queue_size=queue_size,
            now=now,
            mode="capr",
        )
        for elevator in cars
    )
    by_car = {evaluation.elevator_id: evaluation for evaluation in evaluations}
    car_by_id = {elevator.elevator_id: elevator for elevator in cars}
    values: list[float] = []
    groups: dict[str, list[int]] = {
        "eta": [],
        "load": [],
        "capacity": [],
        "age": [],
        "prepositioning": [],
        "route": [],
    }

    def add(value: float, *feature_groups: str) -> None:
        index = len(values)
        values.append(float(value))
        for group in feature_groups:
            groups[group].append(index)

    add((call.floor - 1) / max(1, config.floors - 1))
    add(float(call.direction))
    add(min(max(0.0, now - call.created_at), 180.0) / 180.0, "age")
    add(min(queue_size, config.elevator_capacity * 2) / (config.elevator_capacity * 2))
    add((call.destination or 0) / config.floors)
    for car_id in CAR_IDS:
        add(1.0 if call.assigned_elevator == car_id else 0.0)
    for scenario_name in SCENARIOS:
        add(1.0 if scenario == scenario_name else 0.0, "prepositioning")

    for car_id in CAR_IDS:
        elevator = car_by_id.get(car_id)
        evaluation = by_car.get(car_id)
        if elevator is None or evaluation is None:
            for _ in range(10):
                add(0.0)
            continue
        add(1.0)
        add((elevator.floor - 1) / max(1, config.floors - 1))
        add(float(elevator.direction))
        add(elevator.load_ratio, "load")
        add(min(len(elevator.stops), 8) / 8.0, "route")
        add(_phase_code(elevator))
        add(min(evaluation.pickup_eta, 120.0) / 120.0, "eta")
        add(min(evaluation.route_cost, 240.0) / 240.0, "eta", "route")
        add(evaluation.residual_capacity / max(1, elevator.capacity), "capacity")
        hotspot = parking_hotspot(scenario, elevator.bank, elevator.elevator_id)
        add(abs(elevator.floor - hotspot) / max(1, config.floors - 1), "prepositioning")

    disabled = set(ablations)
    for group in disabled:
        for index in groups.get(group, ()):  # unknown groups are intentionally harmless.
            values[index] = 0.0

    action_mask = [False] * ACTION_COUNT
    for action, car_id in enumerate(CAR_IDS):
        evaluation = by_car.get(car_id)
        action_mask[action] = bool(evaluation is not None and evaluation.feasible)
    feasible_car_exists = any(action_mask[:-1])
    action_mask[HOLD_ACTION] = call.assigned_elevator is not None or not feasible_car_exists
    return DecisionObservation(
        values=tuple(values),
        action_mask=tuple(action_mask),
        evaluations=evaluations,
        feature_groups={key: tuple(indices) for key, indices in groups.items()},
    )


OBSERVATION_SIZE = 17 + len(CAR_IDS) * 10


def masked_argmax(values: Sequence[float], mask: Sequence[bool]) -> int:
    eligible = [index for index, allowed in enumerate(mask) if allowed]
    if not eligible:
        return HOLD_ACTION
    return min(eligible, key=lambda index: (-float(values[index]), index))


class DuelingQNetwork:
    """Small dependency-free dueling Q-network with a single ReLU hidden layer."""

    def __init__(
        self,
        input_size: int = OBSERVATION_SIZE,
        action_count: int = ACTION_COUNT,
        hidden_size: int = 32,
        *,
        seed: int = 0,
    ) -> None:
        self.input_size = input_size
        self.action_count = action_count
        self.hidden_size = hidden_size
        rng = random.Random(seed)
        input_scale = 1.0 / math.sqrt(max(1, input_size))
        head_scale = 1.0 / math.sqrt(max(1, hidden_size))
        self.w1 = [
            [rng.uniform(-input_scale, input_scale) for _ in range(input_size)]
            for _ in range(hidden_size)
        ]
        self.b1 = [0.0 for _ in range(hidden_size)]
        self.w_value = [rng.uniform(-head_scale, head_scale) for _ in range(hidden_size)]
        self.b_value = 0.0
        self.w_advantage = [
            [rng.uniform(-head_scale, head_scale) for _ in range(hidden_size)]
            for _ in range(action_count)
        ]
        self.b_advantage = [0.0 for _ in range(action_count)]

    def _hidden(self, state: Sequence[float]) -> tuple[list[float], list[float]]:
        if len(state) != self.input_size:
            raise ValueError(f"expected {self.input_size} observation values, got {len(state)}")
        pre = [
            self.b1[row] + sum(weight * float(value) for weight, value in zip(self.w1[row], state))
            for row in range(self.hidden_size)
        ]
        return pre, [max(0.0, value) for value in pre]

    def q_values(self, state: Sequence[float]) -> list[float]:
        _, hidden = self._hidden(state)
        value = self.b_value + sum(weight * activation for weight, activation in zip(self.w_value, hidden))
        advantages = [
            self.b_advantage[action]
            + sum(weight * activation for weight, activation in zip(self.w_advantage[action], hidden))
            for action in range(self.action_count)
        ]
        mean_advantage = sum(advantages) / self.action_count
        return [value + advantage - mean_advantage for advantage in advantages]

    @staticmethod
    def _clip(value: float, limit: float = 5.0) -> float:
        return max(-limit, min(limit, value))

    def train_one(
        self,
        state: Sequence[float],
        action: int,
        target: float,
        learning_rate: float,
    ) -> float:
        pre, hidden = self._hidden(state)
        q_values = self.q_values(state)
        error = self._clip(q_values[action] - target, 20.0)
        old_value_weights = list(self.w_value)
        old_advantage_weights = [list(row) for row in self.w_advantage]
        advantage_gradients = [
            error * ((1.0 if index == action else 0.0) - 1.0 / self.action_count)
            for index in range(self.action_count)
        ]

        for hidden_index in range(self.hidden_size):
            self.w_value[hidden_index] -= learning_rate * self._clip(error * hidden[hidden_index])
        self.b_value -= learning_rate * self._clip(error)
        for output in range(self.action_count):
            gradient = advantage_gradients[output]
            for hidden_index in range(self.hidden_size):
                self.w_advantage[output][hidden_index] -= (
                    learning_rate * self._clip(gradient * hidden[hidden_index])
                )
            self.b_advantage[output] -= learning_rate * self._clip(gradient)

        hidden_gradient = []
        for hidden_index in range(self.hidden_size):
            gradient = error * old_value_weights[hidden_index]
            gradient += sum(
                advantage_gradients[output] * old_advantage_weights[output][hidden_index]
                for output in range(self.action_count)
            )
            hidden_gradient.append(gradient if pre[hidden_index] > 0.0 else 0.0)
        for hidden_index, gradient in enumerate(hidden_gradient):
            clipped = self._clip(gradient)
            for input_index, value in enumerate(state):
                self.w1[hidden_index][input_index] -= (
                    learning_rate * self._clip(clipped * float(value))
                )
            self.b1[hidden_index] -= learning_rate * clipped
        return 0.5 * error * error

    def copy_from(self, other: "DuelingQNetwork") -> None:
        if (self.input_size, self.action_count, self.hidden_size) != (
            other.input_size,
            other.action_count,
            other.hidden_size,
        ):
            raise ValueError("network shapes must match")
        self.w1 = [list(row) for row in other.w1]
        self.b1 = list(other.b1)
        self.w_value = list(other.w_value)
        self.b_value = other.b_value
        self.w_advantage = [list(row) for row in other.w_advantage]
        self.b_advantage = list(other.b_advantage)

    def to_dict(self) -> dict[str, object]:
        return {
            "input_size": self.input_size,
            "action_count": self.action_count,
            "hidden_size": self.hidden_size,
            "w1": self.w1,
            "b1": self.b1,
            "w_value": self.w_value,
            "b_value": self.b_value,
            "w_advantage": self.w_advantage,
            "b_advantage": self.b_advantage,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "DuelingQNetwork":
        network = cls(
            input_size=int(payload["input_size"]),
            action_count=int(payload["action_count"]),
            hidden_size=int(payload["hidden_size"]),
        )
        network.w1 = [[float(value) for value in row] for row in payload["w1"]]  # type: ignore[index]
        network.b1 = [float(value) for value in payload["b1"]]  # type: ignore[arg-type]
        network.w_value = [float(value) for value in payload["w_value"]]  # type: ignore[arg-type]
        network.b_value = float(payload["b_value"])
        network.w_advantage = [
            [float(value) for value in row] for row in payload["w_advantage"]  # type: ignore[index]
        ]
        network.b_advantage = [float(value) for value in payload["b_advantage"]]  # type: ignore[arg-type]
        return network


@dataclass(frozen=True, slots=True)
class Transition:
    state: tuple[float, ...]
    action: int
    reward: float
    next_state: tuple[float, ...]
    next_mask: tuple[bool, ...]
    done: bool


class ReplayBuffer:
    def __init__(self, capacity: int = 10_000) -> None:
        self.capacity = capacity
        self.items: list[Transition] = []
        self.position = 0

    def append(self, transition: Transition) -> None:
        if len(self.items) < self.capacity:
            self.items.append(transition)
            return
        self.items[self.position] = transition
        self.position = (self.position + 1) % self.capacity

    def sample(self, count: int, rng: random.Random) -> list[Transition]:
        return rng.sample(self.items, min(count, len(self.items)))

    def __len__(self) -> int:
        return len(self.items)


class DuelingDoubleDQNAgent:
    def __init__(
        self,
        *,
        seed: int = 0,
        hidden_size: int = 24,
        gamma: float = 0.98,
        learning_rate: float = 0.002,
        batch_size: int = 8,
        target_sync_steps: int = 50,
        train_frequency: int = 4,
        replay_capacity: int = 10_000,
    ) -> None:
        self.rng = random.Random(seed)
        self.online = DuelingQNetwork(hidden_size=hidden_size, seed=seed)
        self.target = DuelingQNetwork(hidden_size=hidden_size, seed=seed + 1)
        self.target.copy_from(self.online)
        self.gamma = gamma
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.target_sync_steps = target_sync_steps
        self.train_frequency = train_frequency
        self.replay = ReplayBuffer(replay_capacity)
        self.gradient_steps = 0
        self.environment_steps = 0
        self.loss_history: list[float] = []

    def act(self, state: Sequence[float], mask: Sequence[bool], epsilon: float) -> int:
        eligible = [index for index, allowed in enumerate(mask) if allowed]
        if not eligible:
            return HOLD_ACTION
        if self.rng.random() < epsilon:
            return self.rng.choice(eligible)
        return masked_argmax(self.online.q_values(state), mask)

    def observe(self, transition: Transition) -> float | None:
        self.replay.append(transition)
        self.environment_steps += 1
        if (
            len(self.replay) < self.batch_size
            or self.environment_steps % self.train_frequency != 0
        ):
            return None
        losses = []
        for sample in self.replay.sample(self.batch_size, self.rng):
            target_value = sample.reward
            if not sample.done and any(sample.next_mask):
                next_action = masked_argmax(
                    self.online.q_values(sample.next_state),
                    sample.next_mask,
                )
                target_value += self.gamma * self.target.q_values(sample.next_state)[next_action]
            losses.append(
                self.online.train_one(
                    sample.state,
                    sample.action,
                    target_value,
                    self.learning_rate,
                )
            )
        self.gradient_steps += 1
        if self.gradient_steps % self.target_sync_steps == 0:
            self.target.copy_from(self.online)
        loss = sum(losses) / len(losses)
        self.loss_history.append(loss)
        return loss


@dataclass(slots=True)
class ManualDispatchPolicy:
    name: str = "rl_environment"
    immediate_reassignment: bool = True
    continuous_reassignment: bool = True

    def decide(self, *args: object, **kwargs: object) -> DispatchDecision:
        return DispatchDecision(None, (), "manual environment owns dispatch")

    def parking_floor(self, elevator: Elevator, scenario: str) -> int | None:
        return parking_hotspot(scenario, elevator.bank, elevator.elevator_id)


class ElevatorDispatchEnv(GymEnvBase):
    """Gymnasium-compatible interactive MDP over real simulator dispatch decisions."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        *,
        scenario: str = "normal",
        seed: int = 1,
        episode_seconds: int = 180,
        decision_interval_seconds: int = 1,
        control_mode: str = "conventional",
        reward_weights: RewardWeights | None = None,
        ablations: Iterable[str] = (),
    ) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario: {scenario}")
        self.scenario = scenario
        self.seed_value = seed
        self.episode_seconds = episode_seconds
        self.decision_interval_seconds = decision_interval_seconds
        self.control_mode = control_mode
        self.reward_weights = reward_weights or RewardWeights()
        self.ablations = tuple(ablations)
        self.action_space = spaces.Discrete(ACTION_COUNT)
        try:
            self.observation_space = spaces.Box(
                low=-1.0,
                high=1.0,
                shape=(OBSERVATION_SIZE,),
                dtype=float,
            )
        except TypeError:  # dependency-free fallback Box has no dtype argument.
            self.observation_space = spaces.Box(-1.0, 1.0, (OBSERVATION_SIZE,))
        self.simulation: ElevatorSimulation | None = None
        self.current_key: CallKey | None = None
        self.current_observation: DecisionObservation | None = None
        self._last_energy = 0.0
        self._last_capacity_misses = 0
        self._last_served = 0

    def _energy_proxy(self) -> float:
        assert self.simulation is not None
        counts = self.simulation.ledger.counts()
        distance_m = sum(
            elevator.distance_travelled * self.simulation.config.floor_height_m
            for elevator in self.simulation.elevators
        )
        return distance_m + 8.0 * counts.get("car_depart", 0) + 2.0 * counts.get("car_arrive", 0)

    def _decision_key(self) -> CallKey | None:
        assert self.simulation is not None
        calls = list(self.simulation.hall_calls.items())
        if not calls:
            return None
        unassigned = [(key, call) for key, call in calls if call.assigned_elevator is None]
        if unassigned:
            return min(unassigned, key=lambda item: (item[1].created_at, item[0]))[0]
        eligible = [
            (key, call)
            for key, call in calls
            if self.simulation.sim_time - call.last_evaluated_at
            >= self.simulation.config.reassignment_interval_seconds
        ]
        if not eligible:
            return None
        return min(eligible, key=lambda item: (item[1].last_evaluated_at, item[1].created_at, item[0]))[0]

    def _advance_to_decision(self) -> None:
        assert self.simulation is not None
        self.current_key = self._decision_key()
        while self.current_key is None and self.simulation.sim_time < self.episode_seconds:
            self.simulation.step(1)
            self.current_key = self._decision_key()
        self.current_observation = self._observe_current()

    def _observe_current(self) -> DecisionObservation | None:
        assert self.simulation is not None
        if self.current_key is None:
            return None
        call = self.simulation.hall_calls.get(self.current_key)
        if call is None:
            return None
        return build_decision_observation(
            call,
            self.simulation.compatible_candidates(self.current_key),
            self.simulation.config,
            queue_size=self.simulation.call_queue_size(self.current_key),
            now=self.simulation.sim_time,
            scenario=self.scenario,
            ablations=self.ablations,
        )

    def _info(self) -> dict[str, object]:
        assert self.simulation is not None
        observation = self.current_observation
        return {
            "action_mask": list(observation.action_mask if observation else (False,) * ACTION_COUNT),
            "sim_time": self.simulation.sim_time,
            "call_key": list(self.current_key) if self.current_key is not None else None,
            "trace_digest": self.simulation.trace.digest if self.simulation.trace is not None else None,
        }

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, object] | None = None,
    ) -> tuple[tuple[float, ...], dict[str, object]]:
        del options
        if seed is not None:
            self.seed_value = seed
        config = SimulationConfig(control_mode=self.control_mode)
        trace = generate_scenario_trace(self.scenario, self.episode_seconds, self.seed_value)
        self.simulation = ElevatorSimulation(
            scenario=self.scenario,
            seed=self.seed_value,
            config=config,
            trace=trace,
            policy=ManualDispatchPolicy(),
            auto_dispatch=False,
        )
        self._last_energy = 0.0
        self._last_capacity_misses = 0
        self._last_served = 0
        self._advance_to_decision()
        values = self.current_observation.values if self.current_observation else (0.0,) * OBSERVATION_SIZE
        return values, self._info()

    def _reward(self) -> tuple[float, dict[str, float]]:
        assert self.simulation is not None
        now = self.simulation.sim_time
        waits = [max(0.0, now - passenger.created_at) for passenger in self.simulation.waiting]
        mean_wait = sum(waits) / len(waits) if waits else 0.0
        tail_wait = max(waits, default=0.0)
        by_floor: dict[int, list[float]] = {}
        for passenger, wait in zip(self.simulation.waiting, waits):
            by_floor.setdefault(passenger.origin, []).append(wait)
        floor_means = [sum(values) / len(values) for values in by_floor.values() if values]
        floor_gap = max(floor_means, default=0.0) - min(floor_means, default=0.0)
        energy = self._energy_proxy()
        energy_delta = max(0.0, energy - self._last_energy)
        misses = self.simulation.metrics.missed_capacity
        miss_delta = max(0, misses - self._last_capacity_misses)
        served = self.simulation.metrics.served_count
        served_delta = max(0, served - self._last_served)
        self._last_energy = energy
        self._last_capacity_misses = misses
        self._last_served = served
        components = {
            "mean_wait": -self.reward_weights.mean_wait * mean_wait,
            "tail_wait": -self.reward_weights.tail_wait * tail_wait,
            "floor_gap": -self.reward_weights.floor_gap * floor_gap,
            "capacity_miss": -self.reward_weights.capacity_miss * miss_delta,
            "energy": -self.reward_weights.energy * energy_delta,
            "served": self.reward_weights.served * served_delta,
        }
        return sum(components.values()), components

    def step(
        self,
        action: int,
    ) -> tuple[tuple[float, ...], float, bool, bool, dict[str, object]]:
        if self.simulation is None or self.current_key is None or self.current_observation is None:
            raise RuntimeError("reset() must produce an active decision before step()")
        if not self.action_space.contains(action):
            raise ValueError(f"action must be in [0, {ACTION_COUNT - 1}]")
        observation = self.current_observation
        if not observation.action_mask[action]:
            raise ValueError(f"action {action} is infeasible under the current action mask")
        call = self.simulation.hall_calls.get(self.current_key)
        if call is None:
            raise RuntimeError("active call disappeared before action application")
        chosen_id = None if action == HOLD_ACTION else CAR_IDS[action]
        if action == HOLD_ACTION and call.assigned_elevator is not None:
            chosen_id = call.assigned_elevator
        decision = DispatchDecision(
            chosen_elevator_id=chosen_id,
            evaluations=observation.evaluations,
            reason=(
                f"M5 external action {action}: "
                f"{'hold' if action == HOLD_ACTION else CAR_IDS[action]}"
            ),
        )
        self.simulation.apply_external_decision(self.current_key, decision)
        self.simulation.step(self.decision_interval_seconds)
        self._advance_to_decision()
        reward, components = self._reward()
        truncated = self.simulation.sim_time >= self.episode_seconds
        next_values = (
            self.current_observation.values
            if self.current_observation is not None
            else (0.0,) * OBSERVATION_SIZE
        )
        info = self._info()
        info["reward_components"] = components
        info["audit"] = self.simulation.audit()
        return next_values, reward, False, truncated, info

    def final_metrics(self) -> dict[str, float | int | dict[str, float]]:
        if self.simulation is None:
            raise RuntimeError("environment has not been reset")
        return analyze_simulation(self.simulation)


class LearnedDispatchPolicy:
    name = "rl"
    immediate_reassignment = True
    continuous_reassignment = True

    def __init__(
        self,
        network: DuelingQNetwork,
        *,
        scenario: str,
        ablations: Iterable[str] = (),
    ) -> None:
        self.network = network
        self.scenario = scenario
        self.ablations = tuple(ablations)

    def decide(
        self,
        call: HallCall,
        elevators: Iterable[Elevator],
        config: SimulationConfig,
        *,
        queue_size: int,
        now: float,
    ) -> DispatchDecision:
        observation = build_decision_observation(
            call,
            elevators,
            config,
            queue_size=queue_size,
            now=now,
            scenario=self.scenario,
            ablations=self.ablations,
        )
        q_values = self.network.q_values(observation.values)
        action = masked_argmax(q_values, observation.action_mask)
        chosen_id = None if action == HOLD_ACTION else CAR_IDS[action]
        if action == HOLD_ACTION and call.assigned_elevator is not None:
            chosen_id = call.assigned_elevator
        return DispatchDecision(
            chosen_elevator_id=chosen_id,
            evaluations=observation.evaluations,
            reason=(
                f"{chosen_id or 'hold'} selected by M5 dueling DDQN; "
                f"action={action}; q={q_values[action]:.4f}"
            ),
        )

    def parking_floor(self, elevator: Elevator, scenario: str) -> int | None:
        return parking_hotspot(scenario, elevator.bank, elevator.elevator_id)


def save_model_artifact(
    path: Path,
    network: DuelingQNetwork,
    *,
    metadata: dict[str, object],
) -> None:
    payload = {
        "schema": "elevator-queue-lab.m5-ddqn.v1",
        "architecture": "dueling-double-dqn",
        "observation_size": OBSERVATION_SIZE,
        "actions": [*CAR_IDS, "HOLD"],
        "network": network.to_dict(),
        "metadata": metadata,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_model_artifact(path: Path) -> tuple[DuelingQNetwork, dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "elevator-queue-lab.m5-ddqn.v1":
        raise ValueError("unsupported M5 model artifact schema")
    network = DuelingQNetwork.from_dict(payload["network"])
    return network, dict(payload.get("metadata", {}))


def train_agent(
    *,
    scenarios: Sequence[str],
    seeds: Sequence[int],
    episode_seconds: int,
    epochs: int,
    seed: int,
) -> tuple[DuelingDoubleDQNAgent, dict[str, object]]:
    agent = DuelingDoubleDQNAgent(seed=seed)
    episode_log: list[dict[str, object]] = []
    total_episodes = max(1, epochs * len(scenarios) * len(seeds))
    episode_index = 0
    for epoch in range(epochs):
        for scenario in scenarios:
            for passenger_seed in seeds:
                env = ElevatorDispatchEnv(
                    scenario=scenario,
                    seed=passenger_seed,
                    episode_seconds=episode_seconds,
                )
                state, info = env.reset(seed=passenger_seed)
                total_reward = 0.0
                decisions = 0
                while True:
                    progress = episode_index / max(1, total_episodes - 1)
                    epsilon = max(0.08, 0.55 * (1.0 - progress))
                    mask = tuple(bool(value) for value in info["action_mask"])
                    action = agent.act(state, mask, epsilon)
                    next_state, reward, _, truncated, next_info = env.step(action)
                    next_mask = tuple(bool(value) for value in next_info["action_mask"])
                    agent.observe(
                        Transition(
                            state=tuple(state),
                            action=action,
                            reward=reward,
                            next_state=tuple(next_state),
                            next_mask=next_mask,
                            done=truncated,
                        )
                    )
                    total_reward += reward
                    decisions += 1
                    state, info = next_state, next_info
                    if truncated:
                        break
                metrics = env.final_metrics()
                episode_log.append(
                    {
                        "epoch": epoch,
                        "scenario": scenario,
                        "seed": passenger_seed,
                        "reward": round(total_reward, 6),
                        "decisions": decisions,
                        "avg_wait": round(float(metrics["avg_wait"]), 6),
                        "p95_wait": round(float(metrics["p95_wait"]), 6),
                        "energy_proxy": round(float(metrics["energy_proxy"]), 6),
                        "trace_digest": info["trace_digest"],
                    }
                )
                episode_index += 1
    return agent, {
        "training_seed": seed,
        "training_scenarios": list(scenarios),
        "training_passenger_seeds": list(seeds),
        "episode_seconds": episode_seconds,
        "epochs": epochs,
        "gradient_steps": agent.gradient_steps,
        "final_loss": round(agent.loss_history[-1], 8) if agent.loss_history else None,
        "episodes": episode_log,
    }


EVALUATION_METRICS = (
    "avg_wait",
    "p95_wait",
    "p99_wait",
    "worst_floor_mean_wait",
    "energy_proxy",
    "capacity_misses",
    "unfinished",
)


def evaluate_learned_policy(
    network: DuelingQNetwork,
    *,
    scenarios: Sequence[str],
    seeds: Sequence[int],
    seconds: int,
    ablations: Iterable[str] = (),
) -> dict[str, object]:
    policies = ("collective", "capr", "rl")
    raw_runs: list[dict[str, object]] = []
    for scenario in scenarios:
        for passenger_seed in seeds:
            trace = generate_scenario_trace(scenario, seconds, passenger_seed)
            for policy_name in policies:
                if policy_name == "rl":
                    policy = LearnedDispatchPolicy(
                        network,
                        scenario=scenario,
                        ablations=ablations,
                    )
                    simulation = ElevatorSimulation(
                        scenario=scenario,
                        seed=passenger_seed,
                        trace=trace,
                        policy=policy,
                    )
                else:
                    simulation = ElevatorSimulation(
                        scenario=scenario,
                        policy_name=policy_name,
                        seed=passenger_seed,
                        trace=trace,
                    )
                simulation.run(seconds)
                audit = simulation.audit()
                if not audit["ok"]:
                    raise RuntimeError(
                        f"M5 evaluation audit failed {scenario}/{policy_name}/{passenger_seed}: {audit}"
                    )
                raw_runs.append(
                    {
                        "scenario": scenario,
                        "policy": policy_name,
                        "seed": passenger_seed,
                        "trace_digest": trace.digest,
                        **analyze_simulation(simulation),
                    }
                )

    summaries: list[dict[str, object]] = []
    for scenario in scenarios:
        scenario_rows = [row for row in raw_runs if row["scenario"] == scenario]
        collective_rows = [row for row in scenario_rows if row["policy"] == "collective"]
        collective_means = {
            metric: sum(float(row[metric]) for row in collective_rows) / len(collective_rows)
            for metric in EVALUATION_METRICS
        }
        for policy_name in policies:
            rows = [row for row in scenario_rows if row["policy"] == policy_name]
            metrics = {metric: summarize_metric(rows, metric) for metric in EVALUATION_METRICS}
            means = {metric: float(metrics[metric]["mean"]) for metric in EVALUATION_METRICS}
            classification = (
                "reference"
                if policy_name == "collective"
                else guardrail_classification(means, collective_means)
            )
            summaries.append(
                {
                    "scenario": scenario,
                    "policy": policy_name,
                    "runs": len(rows),
                    "guardrail_classification": classification,
                    "metrics": metrics,
                    "paired_vs_collective": {
                        metric: paired_comparison(rows, collective_rows, metric)
                        for metric in (
                            "avg_wait",
                            "p95_wait",
                            "p99_wait",
                            "worst_floor_mean_wait",
                            "energy_proxy",
                        )
                    },
                }
            )
    return {
        "schema": "elevator-queue-lab.m5-evaluation.v1",
        "common_random_numbers": True,
        "scenarios": list(scenarios),
        "seeds": list(seeds),
        "seconds": seconds,
        "ablations": list(ablations),
        "summaries": summaries,
        "raw_runs": raw_runs,
    }


def model_verdict(evaluation: dict[str, object]) -> dict[str, object]:
    summaries = evaluation["summaries"]
    rl_rows = [row for row in summaries if row["policy"] == "rl"]  # type: ignore[index]
    candidate_scenarios = [
        row["scenario"]
        for row in rl_rows
        if row["guardrail_classification"] == "candidate_improvement"
    ]
    failures = [
        row["scenario"]
        for row in rl_rows
        if row["guardrail_classification"] != "candidate_improvement"
    ]
    accepted = bool(rl_rows) and not failures
    return {
        "accepted_as_general_improvement": accepted,
        "candidate_improvement_scenarios": candidate_scenarios,
        "failed_or_tradeoff_scenarios": failures,
        "interpretation": (
            "held-out evidence supports a general learned-controller improvement"
            if accepted
            else "held-out evidence does not support a general learned-controller superiority claim"
        ),
    }
