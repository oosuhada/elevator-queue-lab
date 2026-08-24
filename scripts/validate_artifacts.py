from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.artifacts import build_artifact_catalog, build_run_artifact, build_trace_manifest
from app.simulator import ElevatorSimulation
from app.trace import generate_trace


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"artifact validation failed: {message}")


def validate_required(payload: dict[str, object], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    require(schema.get("type") == "object", f"schema must describe an object: {schema_path}")
    for key in schema.get("required", []):
        require(key in payload, f"{schema_path.name} required key missing: {key}")


def main() -> None:
    expected = {
        "evidence/m3-regression-baseline.json": "elevator-queue-lab.m3-regression-baseline.v2",
        "evidence/m5-heldout-evaluation.json": "elevator-queue-lab.m5-research-evidence.v1",
        "evidence/m6-heldout-30seed.json": "elevator-queue-lab.m6-heldout-release.v1",
        "evidence/m7-bidirectional-load-sweep.json": "elevator-queue-lab.m7-bidirectional-load-theory.v1",
        "evidence/m7-threshold-validation.json": "elevator-queue-lab.m7-threshold-validation.v1",
        "models/m5-ddqn-baseline.json": "elevator-queue-lab.m5-ddqn.v1",
    }
    for relative, schema in expected.items():
        path = ROOT / relative
        require(path.is_file(), f"missing {relative}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        require(payload.get("schema") == schema, f"unexpected schema for {relative}: {payload.get('schema')}")
        require(len(hashlib.sha256(path.read_bytes()).hexdigest()) == 64, f"invalid sha256 for {relative}")

    trace_a = generate_trace("lunch", duration_seconds=180, seed=42)
    trace_b = generate_trace("lunch", duration_seconds=180, seed=42)
    require(trace_a.digest == trace_b.digest, "same seed did not reproduce passenger trace digest")
    simulation = ElevatorSimulation("lunch", "capr", seed=42, trace=trace_a)
    simulation.step(60)
    manifest = build_trace_manifest(simulation)
    artifact = build_run_artifact(simulation, "run-validation")
    catalog = build_artifact_catalog(simulation, "run-validation")
    validate_required(
        trace_a.to_payload(),
        ROOT / "contracts" / "schemas" / "passenger-trace.schema.json",
    )
    validate_required(
        manifest,
        ROOT / "contracts" / "schemas" / "trace-manifest.schema.json",
    )
    validate_required(
        artifact,
        ROOT / "contracts" / "schemas" / "run-artifact.schema.json",
    )
    require(manifest["sha256"] == trace_a.digest, "manifest does not retain trace SHA identity")
    require(artifact["trace_sha256"] == trace_a.digest, "run artifact does not retain trace SHA identity")
    require(artifact["schema_version"] == "elevator-queue-lab.run.v1", "run schema version changed")
    require(artifact["provenance"]["seed"] == 42, "run provenance seed missing")
    required_artifact_types = {
        "PassengerTraceArtifact",
        "SimulationRunArtifact",
        "DispatchDecisionArtifact",
        "ExperimentArtifact",
        "PolicyEvaluationArtifact",
        "ModelArtifact",
        "TheoryEvidenceArtifact",
    }
    artifact_types = {item["artifact_type"] for item in catalog["artifacts"]}
    require(required_artifact_types.issubset(artifact_types), "artifact catalog is missing required artifact types")
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
    for item in catalog["artifacts"]:
        require(
            required_provenance.issubset(item["provenance"]),
            f"artifact provenance incomplete: {item['artifact_type']}",
        )
    print("artifact validation passed")
    print(f"committed_artifacts={len(expected)}")
    print(f"trace_sha256={trace_a.digest}")


if __name__ == "__main__":
    main()
