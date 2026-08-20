from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .simulator import ElevatorSimulation


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"


class SimulationRunner:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.running = True
        self.speed = 20
        self.scenario = "morning"
        self.policy = "queue_aware"
        self.simulation = ElevatorSimulation(self.scenario, self.policy)
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self) -> None:
        while not self.closed.is_set():
            if self.running:
                with self.lock:
                    self.simulation.step(1)
                time.sleep(max(0.005, 1 / self.speed))
            else:
                time.sleep(0.05)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            result = self.simulation.snapshot()
            result["running"] = self.running
            result["speed"] = self.speed
            return result

    def control(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            action = str(payload.get("action", "update"))
            next_scenario = str(payload.get("scenario", self.scenario))
            next_policy = str(payload.get("policy", self.policy))
            if "speed" in payload:
                self.speed = max(1, min(120, int(payload["speed"])))
            if action == "reset" or next_scenario != self.scenario or next_policy != self.policy:
                self.scenario = next_scenario
                self.policy = next_policy
                self.simulation = ElevatorSimulation(self.scenario, self.policy)
            if action == "pause":
                self.running = False
            elif action in {"start", "reset", "update"}:
                self.running = True
            elif action == "step":
                self.running = False
                self.simulation.step(1)
        return self.snapshot()


class Handler(BaseHTTPRequestHandler):
    runner: SimulationRunner

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/snapshot":
            return self._send_json(self.runner.snapshot())
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
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/control":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        self._send_json(self.runner.control(payload))

    def _send_json(self, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
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

