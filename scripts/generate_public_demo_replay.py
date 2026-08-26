from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.domain import SimulationConfig
from app.server import REPLAY_SCHEMA, compact_replay_frame
from app.simulator import ElevatorSimulation


def build_replay(
    *,
    scenario: str,
    policy: str,
    seed: int,
    duration_seconds: int,
    default_speed: int,
) -> dict[str, object]:
    simulation = ElevatorSimulation(
        scenario,
        policy,
        seed=seed,
        config=SimulationConfig(control_mode="conventional"),
    )
    frames = [compact_replay_frame(simulation)]
    for _ in range(duration_seconds):
        simulation.step(1)
        frames.append(compact_replay_frame(simulation))
    return {
        "schema": REPLAY_SCHEMA,
        "source": "artifact_replay",
        "run_id": f"public-demo-{scenario}-{policy}-seed-{seed}",
        "scenario": scenario,
        "policy": policy,
        "control_mode": "conventional",
        "seed": seed,
        "start_sim_time": frames[0]["sim_time"],
        "end_sim_time": frames[-1]["sim_time"],
        "frame_count": len(frames),
        "default_speed": default_speed,
        "provenance": {
            "generator": "scripts/generate_public_demo_replay.py",
            "engine": "ElevatorSimulation",
            "deterministic_seed": seed,
            "fabricated_chart_data": False,
        },
        "frames": frames,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="shock")
    parser.add_argument("--policy", default="capr")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--default-speed", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evidence" / "public-demo-replay.json",
    )
    args = parser.parse_args()
    if args.duration < 1:
        parser.error("--duration must be positive")
    payload = build_replay(
        scenario=args.scenario,
        policy=args.policy,
        seed=args.seed,
        duration_seconds=args.duration,
        default_speed=args.default_speed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {payload['frame_count']} deterministic frames to {args.output}")


if __name__ == "__main__":
    main()
