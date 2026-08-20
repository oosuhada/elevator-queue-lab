from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    sequence: int
    sim_time: float
    kind: str
    passenger_id: int | None = None
    elevator_id: str | None = None
    floor: int | None = None
    bank: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventLedger:
    def __init__(self) -> None:
        self._events: list[SimulationEvent] = []

    def record(
        self,
        sim_time: float,
        kind: str,
        *,
        passenger_id: int | None = None,
        elevator_id: str | None = None,
        floor: int | None = None,
        bank: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> SimulationEvent:
        event = SimulationEvent(
            sequence=len(self._events) + 1,
            sim_time=sim_time,
            kind=kind,
            passenger_id=passenger_id,
            elevator_id=elevator_id,
            floor=floor,
            bank=bank,
            details=details or {},
        )
        self._events.append(event)
        return event

    @property
    def events(self) -> tuple[SimulationEvent, ...]:
        return tuple(self._events)

    def counts(self) -> dict[str, int]:
        return dict(Counter(event.kind for event in self._events))

    def tail(self, limit: int = 40) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._events[-limit:]]

