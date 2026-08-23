from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .artifacts import build_artifact_catalog, build_run_artifact
from .simulator import ElevatorSimulation


ROOT = Path(__file__).resolve().parents[1]
M3_BASELINE = ROOT / "evidence" / "m3-regression-baseline.json"
M5_EVALUATION = ROOT / "evidence" / "m5-heldout-evaluation.json"
M6_EVALUATION = ROOT / "evidence" / "m6-heldout-30seed.json"
M7_DISCOVERY = ROOT / "evidence" / "m7-bidirectional-load-sweep.json"
M7_VALIDATION = ROOT / "evidence" / "m7-threshold-validation.json"
M5_MODEL = ROOT / "models" / "m5-ddqn-baseline.json"

OBJECT_TYPES = (
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
)

SCENARIOS = ("morning", "lunch", "normal", "evening", "shock", "mixed_day")
POLICIES = ("legacy_sticky", "nearest_car", "collective", "queue_aware", "capr", "rl")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _passenger_objects(simulation: ElevatorSimulation) -> list[dict[str, Any]]:
    by_id: dict[int, dict[str, Any]] = {}
    for event in simulation.ledger.events:
        if event.passenger_id is None:
            continue
        passenger = by_id.setdefault(
            event.passenger_id,
            {
                "id": f"P-{event.passenger_id}",
                "object_type": "Passenger",
                "passenger_id": event.passenger_id,
                "origin": None,
                "destination": None,
                "arrival": None,
                "boarding": None,
                "arrival_at_destination": None,
                "elevator_id": None,
                "status": "waiting",
                "event_sequences": [],
            },
        )
        passenger["event_sequences"].append(event.sequence)
        if event.kind == "arrival":
            passenger["origin"] = event.floor
            passenger["destination"] = event.details.get("destination")
            passenger["arrival"] = event.sim_time
        elif event.kind == "board":
            passenger["boarding"] = event.sim_time
            passenger["elevator_id"] = event.elevator_id
            passenger["status"] = "onboard"
        elif event.kind == "alight":
            passenger["arrival_at_destination"] = event.sim_time
            passenger["status"] = "served"
        elif event.kind == "abandon":
            passenger["status"] = "abandoned"

    for passenger in by_id.values():
        arrival = passenger["arrival"]
        boarding = passenger["boarding"]
        finished = passenger["arrival_at_destination"]
        passenger["wait"] = (
            round(float(boarding) - float(arrival), 3)
            if arrival is not None and boarding is not None
            else None
        )
        passenger["journey_time"] = (
            round(float(finished) - float(arrival), 3)
            if arrival is not None and finished is not None
            else None
        )
    return sorted(by_id.values(), key=lambda item: int(item["passenger_id"]), reverse=True)


def _call_id(call: dict[str, Any]) -> str:
    direction = "up" if int(call["direction"]) > 0 else "down"
    destination = call.get("destination")
    suffix = str(destination) if destination is not None else "any"
    return f"C-{call['bank']}-{call['floor']}-{direction}-{suffix}"


def _hall_call_objects(simulation: ElevatorSimulation) -> list[dict[str, Any]]:
    calls_by_id: dict[str, dict[str, Any]] = {}
    for call in simulation.snapshot()["calls"]:
        item = dict(call)
        item["id"] = _call_id(item)
        item["object_type"] = "HallCall"
        item["status"] = "active"
        item["assignment_history"] = []
        item["reassignment_history"] = []
        item["pickup_history"] = []
        item["final_pickup"] = None
        item["queue_size"] = next(
            (
                simulation.call_queue_size(key)
                for key, active in simulation.hall_calls.items()
                if active.floor == item["floor"]
                and active.direction == item["direction"]
                and active.bank == item["bank"]
                and active.destination == item["destination"]
            ),
            0,
        )
        calls_by_id[item["id"]] = item

    for decision in simulation.decision_history:
        callspec = {
            "bank": decision.get("bank"),
            "floor": decision.get("floor"),
            "direction": decision.get("direction"),
            "destination": decision.get("destination"),
        }
        call_id = _call_id(callspec)
        item = calls_by_id.setdefault(
            call_id,
            {
                "id": call_id,
                "object_type": "HallCall",
                "floor": decision.get("floor"),
                "direction": decision.get("direction"),
                "bank": decision.get("bank"),
                "destination": decision.get("destination"),
                "assigned": None,
                "wait": None,
                "missed": 0,
                "assigned_score": None,
                "queue_size": 0,
                "status": "historical",
                "assignment_history": [],
                "reassignment_history": [],
                "pickup_history": [],
                "final_pickup": None,
            },
        )
        previous = decision.get("current_assignment")
        chosen = decision.get("chosen_elevator_id")
        assignment = {
            "sim_time": decision.get("sim_time"),
            "previous_elevator_id": previous,
            "selected_elevator_id": chosen,
            "queue_size": decision.get("queue_size"),
            "reason": decision.get("reason"),
        }
        item["assignment_history"].append(assignment)
        if previous and chosen and previous != chosen:
            item["reassignment_history"].append(assignment)
        if chosen:
            item["assigned"] = chosen
        if decision.get("queue_size") is not None:
            item["queue_size"] = decision.get("queue_size")

    passengers = {item["passenger_id"]: item for item in _passenger_objects(simulation)}
    destination_mode = simulation.config.control_mode == "destination"
    for event in simulation.ledger.events:
        if event.kind != "board" or event.passenger_id is None:
            continue
        passenger = passengers.get(event.passenger_id)
        if passenger is None:
            continue
        origin = passenger.get("origin")
        destination = passenger.get("destination")
        if not isinstance(origin, int) or not isinstance(destination, int):
            continue
        direction = 1 if destination > origin else -1
        non_lobby_floor = destination if origin == 1 else origin
        bank = "low" if non_lobby_floor <= simulation.config.low_zone_max else "high"
        call_id = _call_id(
            {
                "bank": bank,
                "floor": origin,
                "direction": direction,
                "destination": destination if destination_mode else None,
            }
        )
        item = calls_by_id.get(call_id)
        if item is None:
            continue
        pickup = {
            "sim_time": event.sim_time,
            "passenger_id": event.passenger_id,
            "elevator_id": event.elevator_id,
        }
        item["pickup_history"].append(pickup)
        item["final_pickup"] = pickup
        if item["status"] != "active":
            item["status"] = "served"
    return sorted(
        calls_by_id.values(),
        key=lambda item: float(item["assignment_history"][-1]["sim_time"] if item["assignment_history"] else 0),
        reverse=True,
    )


def _decision_objects(simulation: ElevatorSimulation) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for index, decision in enumerate(simulation.decision_history, start=1):
        item = dict(decision)
        item["id"] = f"D-{index}"
        item["object_type"] = "DispatchDecision"
        item["policy"] = simulation.policy_name
        item["timestamp"] = item.get("sim_time")
        callspec = {
            "bank": item.get("bank"),
            "floor": item.get("floor"),
            "direction": item.get("direction"),
            "destination": item.get("destination"),
        }
        item["hall_call_id"] = _call_id(callspec)
        decisions.append(item)
    return list(reversed(decisions))


def build_objects(
    simulation: ElevatorSimulation,
    run_id: str,
    object_type: str | None = None,
) -> dict[str, Any]:
    """Project simulator/evidence state into browseable workbench objects."""

    snapshot = simulation.snapshot()
    m3 = _load(M3_BASELINE) if M3_BASELINE.is_file() else {"scenarios": {}}
    m5 = _load(M5_EVALUATION) if M5_EVALUATION.is_file() else {}
    model = _load(M5_MODEL) if M5_MODEL.is_file() else {}
    collections: dict[str, list[dict[str, Any]]] = {
        "Elevator": [
            {"id": item["id"], "object_type": "Elevator", **item}
            for item in snapshot["elevators"]
        ],
        "Passenger": _passenger_objects(simulation),
        "HallCall": _hall_call_objects(simulation),
        "DispatchDecision": _decision_objects(simulation),
        "SimulationRun": [
            {
                "id": run_id,
                "object_type": "SimulationRun",
                **build_run_artifact(simulation, run_id),
            }
        ],
        "Scenario": [
            {"id": f"scenario:{name}", "object_type": "Scenario", "name": name}
            for name in SCENARIOS
        ],
        "Policy": [
            {"id": f"policy:{name}", "object_type": "Policy", "name": name}
            for name in POLICIES
        ],
        "Experiment": [
            {
                "id": f"experiment:m3:{name}",
                "object_type": "Experiment",
                "scenario": name,
                "source": "evidence/m3-regression-baseline.json",
                "policies": list(payload.get("policies", {})),
            }
            for name, payload in m3.get("scenarios", {}).items()
        ],
        "Model": [
            {
                "id": "model:m5-ddqn-baseline",
                "object_type": "Model",
                "schema": model.get("schema"),
                "architecture": model.get("architecture"),
                "observation_size": model.get("observation_size"),
                "actions": model.get("actions", []),
                "metadata": model.get("metadata", {}),
                "held_out_verdict": m5.get("verdict", {}),
            }
        ] if model else [],
        "Evidence": [
            {
                "id": f"evidence:{path.name}",
                "object_type": "Evidence",
                "source": str(path.relative_to(ROOT)),
                "schema": _load(path).get("schema"),
            }
            for path in (M3_BASELINE, M5_EVALUATION, M6_EVALUATION)
            if path.is_file()
        ],
        "TheoryEvidence": [
            {
                "id": f"theory:{path.stem}",
                "object_type": "TheoryEvidence",
                "source": str(path.relative_to(ROOT)),
                "schema": _load(path).get("schema"),
            }
            for path in (M7_DISCOVERY, M7_VALIDATION)
            if path.is_file()
        ],
    }
    selected = collections.get(object_type, []) if object_type else [
        item for name in OBJECT_TYPES for item in collections.get(name, [])
    ]
    return {
        "schema": "elevator-queue-lab.objects.v1",
        "run_id": run_id,
        "object_types": list(OBJECT_TYPES),
        "selected_type": object_type,
        "objects": selected,
        "counts": {name: len(collections.get(name, [])) for name in OBJECT_TYPES},
    }


def build_decision_graph(simulation: ElevatorSimulation, run_id: str) -> dict[str, Any]:
    """Build a graph projection without introducing a graph database."""

    all_passengers = _passenger_objects(simulation)
    boarded = [item for item in all_passengers if item.get("boarding") is not None][:24]
    unboarded = [item for item in all_passengers if item.get("boarding") is None][:16]
    passengers = boarded + unboarded
    decisions = _decision_objects(simulation)[:40]
    decision_call_ids = {str(item["hall_call_id"]) for item in decisions}
    calls = [item for item in _hall_call_objects(simulation) if item["id"] in decision_call_ids]
    snapshot = simulation.snapshot()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()

    def add_node(node_id: str, kind: str, label: str, data: dict[str, Any]) -> None:
        if node_id in seen_nodes:
            return
        seen_nodes.add(node_id)
        nodes.append({"id": node_id, "type": kind, "label": label, "data": data})

    def add_edge(source: str, target: str, relation: str, evidence: str) -> None:
        if source in seen_nodes and target in seen_nodes:
            edges.append(
                {
                    "id": f"{source}->{target}:{relation}",
                    "source": source,
                    "target": target,
                    "relation": relation,
                    "evidence": evidence,
                }
            )

    for elevator in snapshot["elevators"]:
        add_node(elevator["id"], "Elevator", elevator["id"], elevator)
    for call in calls:
        add_node(call["id"], "HallCall", f"{call['floor']}F {'↑' if call['direction'] > 0 else '↓'}", call)
    for passenger in passengers:
        add_node(passenger["id"], "Passenger", passenger["id"], passenger)
    for decision in decisions:
        add_node(decision["id"], "DispatchDecision", decision["id"], decision)
    add_node(
        "metric:wait",
        "WaitMetric",
        "Run wait metrics",
        {
            "avg_wait": snapshot["metrics"]["avg_wait"],
            "p95_wait": snapshot["metrics"]["p95_wait"],
            "max_wait": snapshot["metrics"]["max_wait"],
            "source": "snapshot.metrics",
        },
    )

    for passenger in passengers:
        origin = passenger.get("origin")
        destination = passenger.get("destination")
        if isinstance(origin, int) and isinstance(destination, int):
            expected_direction = 1 if destination > origin else -1
            non_lobby_floor = destination if origin == 1 else origin
            bank = "low" if non_lobby_floor <= simulation.config.low_zone_max else "high"
            passenger_call_id = _call_id(
                {
                    "bank": bank,
                    "floor": origin,
                    "direction": expected_direction,
                    "destination": destination if simulation.config.control_mode == "destination" else None,
                }
            )
            add_edge(passenger["id"], passenger_call_id, "generated", "passenger arrival ledger")
        elevator_id = passenger.get("elevator_id")
        if isinstance(elevator_id, str):
            add_edge(passenger["id"], elevator_id, "boarded", "event ledger board")
            pickup_id = f"pickup:{passenger['id']}"
            add_node(
                pickup_id,
                "Pickup",
                f"Pickup {passenger['id']}",
                {
                    "passenger_id": passenger.get("passenger_id"),
                    "elevator_id": elevator_id,
                    "boarding": passenger.get("boarding"),
                    "wait": passenger.get("wait"),
                    "origin": passenger.get("origin"),
                },
            )
            add_edge(elevator_id, pickup_id, "produced", "event ledger board")
            add_edge(pickup_id, "metric:wait", "contributed_to", "passenger wait sample")
    for decision in decisions:
        hall_call_id = str(decision["hall_call_id"])
        add_edge(hall_call_id, decision["id"], "evaluated_by", "dispatch decision ledger")
        chosen = decision.get("chosen_elevator_id")
        if isinstance(chosen, str):
            add_edge(decision["id"], chosen, "selected", str(decision.get("reason", "")))
        previous = decision.get("current_assignment")
        if isinstance(previous, str) and previous != chosen:
            add_edge(decision["id"], previous, "previous_assignment", "dispatch decision ledger")

    return {
        "schema": "elevator-queue-lab.decision-graph.v1",
        "run_id": run_id,
        "nodes": nodes,
        "edges": edges,
        "provenance": {
            "source": "simulator snapshot + decision ledger + event ledger",
            "database": None,
            "projection": "read_only",
        },
    }


def _compare_with_collective(simulation: ElevatorSimulation) -> tuple[str, list[dict[str, Any]]]:
    if not M3_BASELINE.is_file():
        return "Committed M3 evidence is unavailable.", []
    baseline = _load(M3_BASELINE)
    scenario = baseline.get("scenarios", {}).get(simulation.scenario)
    if not scenario:
        return f"No committed M3 scenario named {simulation.scenario} is available.", []
    policies = scenario.get("policies", {})
    current = policies.get(simulation.policy_name)
    collective = policies.get("collective")
    if current is None or collective is None:
        return "This live policy is not present in the committed M3 comparison artifact.", []
    delta = float(current["avg_wait"]) - float(collective["avg_wait"])
    direction = "lower" if delta < 0 else "higher"
    answer = (
        f"In committed 30-seed M3 evidence for {simulation.scenario}, {simulation.policy_name} "
        f"has mean AWT {current['avg_wait']:.2f}s versus collective {collective['avg_wait']:.2f}s "
        f"({abs(delta):.2f}s {direction}). Guardrail classification: "
        f"{current.get('guardrail_classification', 'unknown')}."
    )
    return answer, [
        {"source": "evidence/m3-regression-baseline.json", "policy": simulation.policy_name, "data": current},
        {"source": "evidence/m3-regression-baseline.json", "policy": "collective", "data": collective},
    ]


def answer_run_question(simulation: ElevatorSimulation, run_id: str, question: str) -> dict[str, Any]:
    """Answer a constrained question from deterministic run evidence only."""

    normalized = question.strip()
    lowered = normalized.lower()
    evidence: list[dict[str, Any]] = []
    limitations = [
        "Explanations report observed simulator evidence and controller reasons; they do not infer unrecorded causal mechanisms.",
        "Committed statistical comparisons describe synthetic scenarios, not a universal elevator-control theorem.",
    ]
    intent = "run_summary"
    answer = (
        f"Run {run_id} is at simulation time {int(simulation.sim_time)}s with policy "
        f"{simulation.policy_name} in the {simulation.scenario} scenario."
    )

    passenger_match = re.search(r"p[- ]?(\d+)", lowered)
    decision_match = re.search(r"d[- ]?(\d+)", lowered)
    if passenger_match:
        intent = "passenger_explanation"
        passenger_id = int(passenger_match.group(1))
        passenger = next(
            (item for item in _passenger_objects(simulation) if item["passenger_id"] == passenger_id),
            None,
        )
        passenger_events = [
            event.to_dict()
            for event in simulation.ledger.events
            if event.passenger_id == passenger_id
        ]
        if passenger is None:
            answer = f"Passenger P-{passenger_id} is not present in the current run ledger."
        else:
            wait = passenger.get("wait")
            wait_text = f" waited {wait:.2f}s" if isinstance(wait, (int, float)) else " has not boarded yet"
            answer = (
                f"Passenger P-{passenger_id}{wait_text}. The recorded lifecycle is "
                f"{passenger['status']} from {passenger['origin']}F to {passenger['destination']}F"
                + (f" on {passenger['elevator_id']}." if passenger.get("elevator_id") else ".")
            )
            evidence.append({"source": "event_ledger", "passenger": passenger, "events": passenger_events})
    elif decision_match:
        intent = "decision_explanation"
        decision_id = f"D-{int(decision_match.group(1))}"
        decision = next((item for item in _decision_objects(simulation) if item["id"] == decision_id), None)
        if decision is None:
            answer = f"Decision {decision_id} is not present in the retained decision ledger."
        else:
            answer = str(decision.get("reason", "No controller reason was recorded."))
            evidence.append({"source": "decision_ledger", "decision": decision})
    elif "compare" in lowered and "collective" in lowered:
        intent = "policy_comparison"
        answer, evidence = _compare_with_collective(simulation)
    elif "reassign" in lowered:
        intent = "reassignment_explanation"
        event = next(
            (event for event in reversed(simulation.ledger.events) if event.kind in {"assignment_invalidated", "reassign"}),
            None,
        )
        if event is None:
            answer = "No reassignment event has been recorded in the current run yet."
        else:
            answer = (
                f"The latest reassignment-related event occurred at {event.sim_time:.2f}s on "
                f"{event.floor}F. Recorded details: {json.dumps(event.details, sort_keys=True)}"
            )
            evidence.append({"source": "event_ledger", "event": event.to_dict()})
    elif "why" in lowered or "choose" in lowered or "selected" in lowered:
        intent = "latest_dispatch_explanation"
        decision = _decision_objects(simulation)[0] if simulation.decision_history else None
        if decision is None:
            answer = "No dispatch decision has been recorded in the current run yet."
        else:
            answer = str(decision.get("reason", "No controller reason was recorded."))
            evidence.append({"source": "decision_ledger", "decision": decision})
    elif "p95" in lowered or "spike" in lowered:
        intent = "tail_metric_explanation"
        metrics = simulation.snapshot()["metrics"]
        answer = (
            f"Current P95 wait is {metrics['p95_wait']:.2f}s with {metrics['current_queue']} passengers waiting. "
            "The run ledger can show coincident capacity misses/reassignments, but this interface does not assign a causal driver without recorded evidence."
        )
        evidence.append({"source": "snapshot.metrics", "metrics": metrics})

    return {
        "schema": "elevator-queue-lab.ask-run.v1",
        "run_id": run_id,
        "question": normalized,
        "intent": intent,
        "answer": answer,
        "evidence": evidence,
        "limitations": limitations,
        "expression_layer": "deterministic",
        "llm_required": False,
    }


def build_models_payload() -> dict[str, Any]:
    model = _load(M5_MODEL)
    evaluation = _load(M5_EVALUATION)
    return {
        "schema": "elevator-queue-lab.models-ui.v1",
        "model": model,
        "evaluation": evaluation,
        "source": {
            "model": "models/m5-ddqn-baseline.json",
            "evaluation": "evidence/m5-heldout-evaluation.json",
        },
    }


def build_artifacts_payload(simulation: ElevatorSimulation, run_id: str) -> dict[str, Any]:
    return build_artifact_catalog(simulation, run_id)
