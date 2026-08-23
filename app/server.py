from __future__ import annotations

import argparse
import copy
import json
import mimetypes
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .artifacts import build_run_artifact
from .domain import SimulationConfig
from .simulator import ElevatorSimulation
from .workbench import (
    answer_run_question,
    build_artifacts_payload,
    build_decision_graph,
    build_models_payload,
    build_objects,
)


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
M3_BASELINE = ROOT / "evidence" / "m3-regression-baseline.json"
M7_DISCOVERY = ROOT / "evidence" / "m7-bidirectional-load-sweep.json"
M7_VALIDATION = ROOT / "evidence" / "m7-threshold-validation.json"
REPLAY_SCHEMA = "elevator-queue-lab.replay.v1"
REPLAY_LIMIT = 600


class SimulationRunner:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.running = True
        self.speed = 20
        self.scenario = "morning"
        self.policy = "capr"
        self.control_mode = "conventional"
        self.run_id = self._new_run_id()
        self.simulation = self._new_simulation()
        self.replay_frames: list[dict[str, Any]] = []
        self.saved_replay: dict[str, Any] | None = None
        self._last_replay_second = -1
        self._record_replay_frame(force=True)
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _new_run_id(self) -> str:
        return f"run-{uuid.uuid4().hex[:12]}"

    def _new_simulation(self) -> ElevatorSimulation:
        return ElevatorSimulation(
            self.scenario,
            self.policy,
            config=SimulationConfig(control_mode=self.control_mode),
        )

    def _loop(self) -> None:
        while not self.closed.is_set():
            if self.running:
                with self.lock:
                    self.simulation.step(1)
                    self._record_replay_frame()
                time.sleep(max(0.005, 1 / self.speed))
            else:
                time.sleep(0.05)

    def _compact_replay_frame(self) -> dict[str, Any]:
        source = self.simulation.snapshot()
        return {
            "scenario": source["scenario"],
            "policy": source["policy"],
            "sim_time": source["sim_time"],
            "clock": source["clock"],
            "metrics": source["metrics"],
            "elevators": source["elevators"],
            "queues": source["queues"],
            "calls": source["calls"],
            "event_tail": source["event_tail"][-12:],
            "decision_tail": source["decision_tail"][-4:],
            "simulation_config": source["simulation_config"],
        }

    def _record_replay_frame(self, *, force: bool = False) -> None:
        second = int(self.simulation.sim_time)
        if not force and second == self._last_replay_second:
            return
        self._last_replay_second = second
        self.replay_frames.append(self._compact_replay_frame())
        if len(self.replay_frames) > REPLAY_LIMIT:
            self.replay_frames = self.replay_frames[-REPLAY_LIMIT:]

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            result = self.simulation.snapshot()
            result["running"] = self.running
            result["speed"] = self.speed
            result["replay_frames"] = len(self.replay_frames)
            result["saved_replay_available"] = self.saved_replay is not None
            return result

    def control(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            action = str(payload.get("action", "update"))
            next_scenario = str(payload.get("scenario", self.scenario))
            next_policy = str(payload.get("policy", self.policy))
            next_control_mode = str(payload.get("control_mode", self.control_mode))
            if next_control_mode not in {"conventional", "destination"}:
                raise ValueError("control_mode must be conventional or destination")
            if "speed" in payload:
                self.speed = max(1, min(120, int(payload["speed"])))
            requires_reset = (
                action in {"reset", "reset_paused"}
                or next_scenario != self.scenario
                or next_policy != self.policy
                or next_control_mode != self.control_mode
            )
            if requires_reset:
                self.scenario = next_scenario
                self.policy = next_policy
                self.control_mode = next_control_mode
                self.run_id = self._new_run_id()
                self.simulation = self._new_simulation()
                self.replay_frames = []
                self._last_replay_second = -1
                self._record_replay_frame(force=True)
            if action in {"pause", "reset_paused"}:
                self.running = False
            elif action in {"start", "reset", "update"}:
                self.running = True
            elif action == "step":
                self.running = False
                self.simulation.step(1)
                self._record_replay_frame()
        return self.snapshot()

    def replay(self) -> dict[str, Any]:
        with self.lock:
            if self.saved_replay is not None:
                return copy.deepcopy(self.saved_replay)
            return self._build_replay_payload(self.replay_frames, source="live_buffer")

    def replay_control(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action", "save"))
        with self.lock:
            if action == "save":
                self.saved_replay = self._build_replay_payload(
                    copy.deepcopy(self.replay_frames),
                    source="saved_run",
                )
            elif action == "clear":
                self.saved_replay = None
            else:
                raise ValueError("replay action must be save or clear")
            return self.replay()

    def _build_replay_payload(
        self,
        frames: list[dict[str, Any]],
        *,
        source: str,
    ) -> dict[str, Any]:
        first = frames[0] if frames else self._compact_replay_frame()
        last = frames[-1] if frames else first
        return {
            "schema": REPLAY_SCHEMA,
            "source": source,
            "scenario": first["scenario"],
            "policy": first["policy"],
            "control_mode": first["simulation_config"]["control_mode"],
            "start_sim_time": first["sim_time"],
            "end_sim_time": last["sim_time"],
            "frame_count": len(frames),
            "frames": frames,
        }

    def experiment(self) -> dict[str, Any]:
        if not M3_BASELINE.is_file():
            raise FileNotFoundError("M3 regression baseline is unavailable")
        baseline = json.loads(M3_BASELINE.read_text(encoding="utf-8"))
        return {
            "schema": "elevator-queue-lab.experiment-ui.v1",
            "source": "evidence/m3-regression-baseline.json",
            "baseline": baseline,
        }

    def theory(self) -> dict[str, Any]:
        missing = [
            str(path.relative_to(ROOT))
            for path in (M7_DISCOVERY, M7_VALIDATION)
            if not path.is_file()
        ]
        if missing:
            raise FileNotFoundError("M7 theory evidence is unavailable: " + ", ".join(missing))
        return {
            "schema": "elevator-queue-lab.theory-ui.v1",
            "discovery": json.loads(M7_DISCOVERY.read_text(encoding="utf-8")),
            "validation": json.loads(M7_VALIDATION.read_text(encoding="utf-8")),
        }

    def run_artifact(self) -> dict[str, Any]:
        with self.lock:
            return build_run_artifact(self.simulation, self.run_id)

    def objects(self, object_type: str | None = None) -> dict[str, Any]:
        with self.lock:
            return build_objects(self.simulation, self.run_id, object_type)

    def graph(self) -> dict[str, Any]:
        with self.lock:
            return build_decision_graph(self.simulation, self.run_id)

    def ask(self, question: str) -> dict[str, Any]:
        with self.lock:
            return answer_run_question(self.simulation, self.run_id, question)

    def artifacts(self) -> dict[str, Any]:
        with self.lock:
            return build_artifacts_payload(self.simulation, self.run_id)


class Handler(BaseHTTPRequestHandler):
    runner: SimulationRunner

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self._send_json(
                {
                    "schema": "elevator-queue-lab.health.v1",
                    "status": "ok",
                }
            )
        if parsed.path == "/api/snapshot":
            return self._send_json(self.runner.snapshot())
        if parsed.path == "/api/replay":
            return self._send_json(self.runner.replay())
        if parsed.path == "/api/experiment":
            try:
                return self._send_json(self.runner.experiment())
            except FileNotFoundError as exc:
                return self._send_json(
                    {"error": str(exc)},
                    status=HTTPStatus.NOT_FOUND,
                )
        if parsed.path == "/api/theory":
            try:
                return self._send_json(self.runner.theory())
            except FileNotFoundError as exc:
                return self._send_json(
                    {"error": str(exc)},
                    status=HTTPStatus.NOT_FOUND,
                )
        if parsed.path == "/api/runs":
            return self._send_json(
                {
                    "schema": "elevator-queue-lab.runs.v1",
                    "runs": [self.runner.run_artifact()],
                }
            )
        if parsed.path == f"/api/runs/{self.runner.run_id}":
            return self._send_json(self.runner.run_artifact())
        if parsed.path == f"/api/runs/{self.runner.run_id}/objects":
            object_type = parse_qs(parsed.query).get("type", [None])[0]
            return self._send_json(self.runner.objects(object_type))
        if parsed.path == f"/api/runs/{self.runner.run_id}/decisions":
            return self._send_json(self.runner.objects("DispatchDecision"))
        if parsed.path == f"/api/runs/{self.runner.run_id}/graph":
            return self._send_json(self.runner.graph())
        if parsed.path == f"/api/runs/{self.runner.run_id}/ask":
            question = parse_qs(parsed.query).get("q", [""])[0]
            return self._send_json(self.runner.ask(question))
        if parsed.path == "/api/artifacts":
            return self._send_json(self.runner.artifacts())
        if parsed.path == "/api/models":
            try:
                return self._send_json(build_models_payload())
            except FileNotFoundError as exc:
                return self._send_json(
                    {"error": str(exc)},
                    status=HTTPStatus.NOT_FOUND,
                )
        path = WEB_ROOT / ("index.html" if parsed.path == "/" else parsed.path.lstrip("/"))
        resolved = path.resolve()
        if not str(resolved).startswith(str(WEB_ROOT.resolve())) or not resolved.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = resolved.read_bytes()
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # The public demo is deployed by replacing this checkout in place. Avoid
        # serving a mixed-version UI (new HTML with stale JS/CSS) through an
        # intermediary cache after deploys. The app is tiny, so freshness is
        # more important here than static-asset caching.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in {"/api/control", "/api/replay"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        try:
            result = (
                self.runner.control(payload)
                if path == "/api/control"
                else self.runner.replay_control(payload)
            )
        except (TypeError, ValueError) as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        self._send_json(result)

    def _send_json(
        self,
        payload: object,
        *,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()
    runner = SimulationRunner()
    handler = type("ElevatorQueueHandler", (Handler,), {"runner": runner})
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Elevator Queue Lab running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    finally:
        runner.closed.set()
        runner.thread.join(timeout=1)
        server.server_close()


if __name__ == "__main__":
    main()
