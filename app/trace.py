from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from .demand import DemandModel


TRACE_SCHEMA = "elevator-queue-lab.passenger-trace.v1"


@dataclass(frozen=True, slots=True)
class DemandEvent:
    at: int
    passenger_id: int
    origin: int
    destination: int


@dataclass(frozen=True, slots=True)
class PassengerTrace:
    scenario: str
    seed: int
    duration_seconds: int
    events: tuple[DemandEvent, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": TRACE_SCHEMA,
            "scenario": self.scenario,
            "seed": self.seed,
            "duration_seconds": self.duration_seconds,
            "events": [asdict(event) for event in self.events],
        }

    def to_json(self) -> str:
        # Canonical separators/sort order make the trace byte-stable for a given model version.
        return json.dumps(
            self.to_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_json(cls, raw: str) -> "PassengerTrace":
        payload = json.loads(raw)
        if payload.get("schema") != TRACE_SCHEMA:
            raise ValueError(f"Unsupported passenger trace schema: {payload.get('schema')}")
        events = tuple(DemandEvent(**event) for event in payload["events"])
        return cls(
            scenario=str(payload["scenario"]),
            seed=int(payload["seed"]),
            duration_seconds=int(payload["duration_seconds"]),
            events=events,
        )


def generate_trace(scenario: str, duration_seconds: int, seed: int) -> PassengerTrace:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    demand = DemandModel(scenario, seed)
    passenger_id = 1
    events: list[DemandEvent] = []
    for second in range(1, duration_seconds + 1):
        for _ in range(demand.arrivals_this_second()):
            origin, destination = demand.trip()
            events.append(
                DemandEvent(
                    at=second,
                    passenger_id=passenger_id,
                    origin=origin,
                    destination=destination,
                )
            )
            passenger_id += 1
    return PassengerTrace(
        scenario=scenario,
        seed=seed,
        duration_seconds=duration_seconds,
        events=tuple(events),
    )

