from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.artifacts import build_passenger_trace_manifest
from app.domain import SimulationConfig
from app.trace import TRACE_SCHEMA, generate_trace


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a canonical passenger OD trace")
    parser.add_argument("--scenario", required=True, choices=("morning", "lunch", "normal", "evening"))
    parser.add_argument("--seconds", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--package-dir",
        type=Path,
        help="optional directory for trace.json + manifest.json + schema.json + validation.json",
    )
    args = parser.parse_args()

    trace = generate_trace(args.scenario, args.seconds, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(trace.to_json() + "\n", encoding="utf-8", newline="\n")
    if args.package_dir is not None:
        args.package_dir.mkdir(parents=True, exist_ok=True)
        trace_path = args.package_dir / "trace.json"
        trace_path.write_text(trace.to_json() + "\n", encoding="utf-8", newline="\n")
        manifest = build_passenger_trace_manifest(trace, SimulationConfig())
        (args.package_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        schema_source = ROOT / "contracts" / "schemas" / "passenger-trace.schema.json"
        (args.package_dir / "schema.json").write_text(
            schema_source.read_text(encoding="utf-8"),
            encoding="utf-8",
            newline="\n",
        )
        validation = {
            "schema": "elevator-queue-lab.trace-validation.v1",
            "valid": True,
            "trace_schema": TRACE_SCHEMA,
            "event_count": len(trace.events),
            "sha256": trace.digest,
            "manifest_sha256_matches": manifest["sha256"] == trace.digest,
        }
        (args.package_dir / "validation.json").write_text(
            json.dumps(validation, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(f"events={len(trace.events)} sha256={trace.digest} output={args.output}")


if __name__ == "__main__":
    main()

