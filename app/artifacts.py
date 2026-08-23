from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .domain import SimulationConfig
from .simulator import ElevatorSimulation
from .trace import PassengerTrace


ROOT = Path(__file__).resolve().parents[1]
SIMULATOR_VERSION = "0.1.0"
ARTIFACT_VERSION = "1.0.0"


def _created_at() -> str:
    """Return an ISO-8601 timestamp for transient artifact envelopes."""

    return datetime.now(UTC).isoformat()


def _sha256_json(payload: object) -> str:
    """Hash a JSON-compatible value with deterministic serialization."""

    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_passenger_trace_manifest(
    trace: PassengerTrace,
    config: SimulationConfig,
) -> dict[str, Any]:
    """Build the canonical versioned manifest for a materialized passenger trace."""

    identity_payload = {
        "scenario": trace.scenario,
        "seed": trace.seed,
        "building": config.as_dict(),
        "trace_sha256": trace.digest,
    }
    return {
        "schema_version": "elevator-queue-lab.trace-manifest.v1",
        "artifact_version": ARTIFACT_VERSION,
        "generator_version": "elevator-queue-lab.demand.v2",
        "seed": trace.seed,
        "scenario": trace.scenario,
        "building_configuration": config.as_dict(),
        "traffic_contract": "office-demand-85-10-5",
        "duration_seconds": trace.duration_seconds,
        "sha256": trace.digest,
        "identity_sha256": _sha256_json(identity_payload),
        "created_at": _created_at(),
        "source": "materialized_trace",
    }


def build_trace_manifest(simulation: ElevatorSimulation) -> dict[str, Any]:
    """Describe the deterministic passenger source without mutating it."""

    if simulation.trace is not None:
        return build_passenger_trace_manifest(simulation.trace, simulation.config)
    identity_payload = {
        "scenario": simulation.scenario,
        "seed": simulation.seed,
        "building": simulation.config.as_dict(),
        "trace_sha256": None,
    }
    return {
        "schema_version": "elevator-queue-lab.trace-manifest.v1",
        "artifact_version": ARTIFACT_VERSION,
        "generator_version": "elevator-queue-lab.demand.v2",
        "seed": simulation.seed,
        "scenario": simulation.scenario,
        "building_configuration": simulation.config.as_dict(),
        "traffic_contract": "office-demand-85-10-5",
        "duration_seconds": int(simulation.sim_time),
        "sha256": None,
        "identity_sha256": _sha256_json(identity_payload),
        "created_at": _created_at(),
        "source": "seeded_demand_generator",
    }


def build_run_artifact(simulation: ElevatorSimulation, run_id: str) -> dict[str, Any]:
    """Create a versioned envelope around the current simulator run."""

    snapshot = simulation.snapshot()
    trace_manifest = build_trace_manifest(simulation)
    created_at = _created_at()
    provenance = {
        "schema_version": "elevator-queue-lab.provenance.v1",
        "artifact_version": ARTIFACT_VERSION,
        "simulator_version": SIMULATOR_VERSION,
        "source": "live_simulator",
        "seed": simulation.seed,
        "scenario": simulation.scenario,
        "policy": simulation.policy_name,
        "config": simulation.config.as_dict(),
        "created_at": created_at,
        "trace_sha256": trace_manifest["sha256"],
        "trace_identity_sha256": trace_manifest["identity_sha256"],
        "evidence_source": None,
        "evidence_sources": [
            "evidence/m3-regression-baseline.json",
            "evidence/m5-heldout-evaluation.json",
            "evidence/m6-heldout-30seed.json",
            "evidence/m7-bidirectional-load-sweep.json",
            "evidence/m7-threshold-validation.json",
        ],
    }
    return {
        "schema_version": "elevator-queue-lab.run.v1",
        "artifact_version": ARTIFACT_VERSION,
        "simulator_version": SIMULATOR_VERSION,
        "run_id": run_id,
        "scenario": simulation.scenario,
        "policy": simulation.policy_name,
        "seed": simulation.seed,
        "sim_time": snapshot["sim_time"],
        "trace_sha256": trace_manifest["sha256"],
        "metrics": snapshot["metrics"],
        "provenance": provenance,
        "trace_manifest": trace_manifest,
        "created_at": created_at,
    }


def build_artifact_catalog(simulation: ElevatorSimulation, run_id: str) -> dict[str, Any]:
    """Expose committed evidence and the live run as typed artifact references."""

    created_at = _created_at()
    trace_manifest = build_trace_manifest(simulation)
    live_provenance = {
        "schema_version": "elevator-queue-lab.provenance.v1",
        "artifact_version": ARTIFACT_VERSION,
        "simulator_version": SIMULATOR_VERSION,
        "source": "live_simulator",
        "seed": simulation.seed,
        "scenario": simulation.scenario,
        "policy": simulation.policy_name,
        "config": simulation.config.as_dict(),
        "created_at": created_at,
        "trace_sha256": trace_manifest["sha256"],
        "evidence_source": None,
    }
    committed = [
        ("ExperimentArtifact", "evidence/m3-regression-baseline.json"),
        ("PolicyEvaluationArtifact", "evidence/m5-heldout-evaluation.json"),
        ("PolicyEvaluationArtifact", "evidence/m6-heldout-30seed.json"),
        ("TheoryEvidenceArtifact", "evidence/m7-bidirectional-load-sweep.json"),
        ("TheoryEvidenceArtifact", "evidence/m7-threshold-validation.json"),
        ("ModelArtifact", "models/m5-ddqn-baseline.json"),
    ]
    artifacts: list[dict[str, Any]] = [
        {
            "artifact_type": "SimulationRunArtifact",
            "schema_version": "elevator-queue-lab.run.v1",
            "artifact_version": ARTIFACT_VERSION,
            "artifact_id": run_id,
            "source": "live_simulator",
            "sha256": None,
            "provenance": dict(live_provenance),
        },
        {
            "artifact_type": "PassengerTraceArtifact",
            "schema_version": trace_manifest["schema_version"],
            "artifact_version": ARTIFACT_VERSION,
            "artifact_id": f"{run_id}:trace",
            "source": trace_manifest["source"],
            "sha256": trace_manifest["sha256"],
            "provenance": {
                **live_provenance,
                "source": trace_manifest["source"],
            },
        },
        {
            "artifact_type": "DispatchDecisionArtifact",
            "schema_version": "elevator-queue-lab.dispatch-decisions.v1",
            "artifact_version": ARTIFACT_VERSION,
            "artifact_id": f"{run_id}:dispatch-decisions",
            "source": "decision_history",
            "sha256": _sha256_json(simulation.decision_history),
            "provenance": {
                **live_provenance,
                "source": "decision_history",
            },
        }
    ]
    for artifact_type, relative_path in committed:
        path = ROOT / relative_path
        if not path.is_file():
            continue
        raw = path.read_bytes()
        payload = json.loads(raw)
        artifacts.append(
            {
                "artifact_type": artifact_type,
                "schema_version": payload.get("schema", "unknown"),
                "artifact_version": ARTIFACT_VERSION,
                "artifact_id": relative_path,
                "source": relative_path,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "provenance": {
                    "schema_version": "elevator-queue-lab.provenance.v1",
                    "artifact_version": ARTIFACT_VERSION,
                    "simulator_version": SIMULATOR_VERSION,
                    "source": relative_path,
                    "seed": None,
                    "scenario": None,
                    "policy": None,
                    "config": None,
                    "created_at": created_at,
                    "trace_sha256": None,
                    "evidence_source": relative_path,
                },
            }
        )
    return {
        "schema": "elevator-queue-lab.artifact-catalog.v1",
        "run_id": run_id,
        "artifacts": artifacts,
    }
