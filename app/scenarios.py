from __future__ import annotations

from dataclasses import dataclass

from .demand import DemandModel
from .trace import DemandEvent, PassengerTrace, generate_trace


SCENARIOS = ("morning", "lunch", "normal", "evening", "shock", "mixed_day")


@dataclass(frozen=True, slots=True)
class ScenarioMetadata:
    name: str
    description: str
    segments: tuple[str, ...]


SCENARIO_METADATA = {
    "morning": ScenarioMetadata("morning", "Lobby-dominant office arrival up-peak", ("morning",)),
    "lunch": ScenarioMetadata("lunch", "Mixed lunch departure/return traffic", ("lunch",)),
    "normal": ScenarioMetadata("normal", "Lower-intensity bidirectional office traffic", ("normal",)),
    "evening": ScenarioMetadata("evening", "Office-floor to lobby down-peak", ("evening",)),
    "shock": ScenarioMetadata(
        "shock",
        "Evening down-peak with a deterministic mid-run extra arrival burst",
        ("evening", "evening_burst"),
    ),
    "mixed_day": ScenarioMetadata(
        "mixed_day",
        "Compressed morning/lunch/normal/evening sequence with persisted segment boundaries",
        ("morning", "lunch", "normal", "evening"),
    ),
}


def generate_scenario_trace(name: str, duration_seconds: int, seed: int) -> PassengerTrace:
    if name not in SCENARIOS:
        raise ValueError(f"Unknown experiment scenario: {name}")
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if name in {"morning", "lunch", "normal", "evening"}:
        return generate_trace(name, duration_seconds, seed)
    if name == "shock":
        return _shock_trace(duration_seconds, seed)
    return _mixed_day_trace(duration_seconds, seed)


def _shock_trace(duration_seconds: int, seed: int) -> PassengerTrace:
    base = generate_trace("evening", duration_seconds, seed)
    extra = DemandModel("evening", seed + 50_000)
    burst_start = max(1, int(duration_seconds * 0.35))
    burst_end = max(burst_start, int(duration_seconds * 0.60))
    events = [
        DemandEvent(
            at=event.at,
            passenger_id=0,
            origin=event.origin,
            destination=event.destination,
        )
        for event in base.events
    ]
    # An extra evening-rate stream is overlaid only during the burst window. This roughly
    # doubles demand there while preserving a deterministic common trace for all controllers.
    for second in range(1, duration_seconds + 1):
        count = extra.arrivals_this_second()
        for _ in range(count):
            origin, destination = extra.trip()
            if burst_start <= second <= burst_end:
                events.append(
                    DemandEvent(
                        at=second,
                        passenger_id=0,
                        origin=origin,
                        destination=destination,
                    )
                )
    events.sort(key=lambda item: (item.at, item.origin, item.destination))
    renumbered = tuple(
        DemandEvent(
            at=event.at,
            passenger_id=index,
            origin=event.origin,
            destination=event.destination,
        )
        for index, event in enumerate(events, start=1)
    )
    return PassengerTrace(
        scenario="shock",
        seed=seed,
        duration_seconds=duration_seconds,
        events=renumbered,
    )


def _mixed_day_trace(duration_seconds: int, seed: int) -> PassengerTrace:
    patterns = ("morning", "lunch", "normal", "evening")
    base_segment = duration_seconds // len(patterns)
    remainder = duration_seconds % len(patterns)
    offset = 0
    passenger_id = 1
    events: list[DemandEvent] = []
    for index, pattern in enumerate(patterns):
        segment_seconds = base_segment + (1 if index < remainder else 0)
        if segment_seconds <= 0:
            continue
        segment = generate_trace(pattern, segment_seconds, seed + index * 10_000)
        for event in segment.events:
            events.append(
                DemandEvent(
                    at=offset + event.at,
                    passenger_id=passenger_id,
                    origin=event.origin,
                    destination=event.destination,
                )
            )
            passenger_id += 1
        offset += segment_seconds
    return PassengerTrace(
        scenario="mixed_day",
        seed=seed,
        duration_seconds=duration_seconds,
        events=tuple(events),
    )
