import { useEffect, useMemo, useState } from "react";
import { ChartRenderer } from "../../components/charts/ChartRenderer";
import { MetricCard } from "../../components/common/MetricCard";
import type { ReplayPayload, SimulationEvent, Snapshot } from "../../contracts/api";
import type { ChartSpec } from "../../contracts/chartSpec";
import { DigitalTwin } from "./DigitalTwin";
import { ReplayTimeline } from "./ReplayTimeline";


interface LiveOperationsProps {
  liveSnapshot: Snapshot;
  onSaveReplay: () => Promise<ReplayPayload>;
  onControl: (payload: Record<string, unknown>) => Promise<void>;
  onInspectionSnapshotChange?: (snapshot: Snapshot) => void;
}

function fmtSeconds(value: number): string {
  return `${Number(value || 0).toFixed(1)}s`;
}

function decisionEvents(events: SimulationEvent[]): SimulationEvent[] {
  return events.filter((event) => ["assign", "reassign", "assignment_invalidated", "full_pass"].includes(event.kind)).slice(-10).reverse();
}

function EventStream({ events, selectedSequence, onSelect }: { events: SimulationEvent[]; selectedSequence: number | null; onSelect: (event: SimulationEvent) => void }) {
  const relevant = decisionEvents(events);
  return (
    <section className="panel-card event-panel">
      <header className="section-heading"><div><span>Decision ledger</span><strong>Dispatch events / physical time</strong></div></header>
      <div id="event-stream" className="event-stream">
        {relevant.length ? relevant.map((event) => (
          <button key={event.sequence} type="button" className={`event event-${event.kind} ${selectedSequence === event.sequence ? "is-selected" : ""}`} onClick={() => onSelect(event)}>
            <time>T+{event.sim_time.toFixed(1)}s</time>
            <b>{event.kind.replaceAll("_", " ").toUpperCase()}</b>
            <span>{event.floor ?? "—"}F · {event.elevator_id ?? "—"}</span>
            {typeof event.details?.reason === "string" ? <small>{event.details.reason}</small> : null}
          </button>
        )) : <span className="muted">No dispatch events yet.</span>}
      </div>
    </section>
  );
}

function ActiveCalls({ snapshot }: { snapshot: Snapshot }) {
  const calls = [...snapshot.calls].sort((a, b) => b.wait - a.wait).slice(0, 12);
  return (
    <section className="panel-card calls-panel">
      <header className="section-heading"><div><span>Hall calls</span><strong>Vertical demand register</strong></div><span>{snapshot.calls.length} calls</span></header>
      <div id="calls" className="call-list">
        {calls.length ? calls.map((call, index) => (
          <article key={`${call.floor}-${call.direction}-${call.destination}-${index}`} className="call" data-floor={call.floor} data-assigned={call.assigned ?? ""}>
            <strong>{call.floor}F {call.direction > 0 ? "↑" : "↓"}{call.destination ? ` → ${call.destination}F` : ""}</strong>
            <span>{call.assigned ?? "unassigned"}{call.assigned_score === null ? "" : ` · ${call.assigned_score.toFixed(1)}`}</span>
            <b className="wait">{call.wait.toFixed(0)}s</b>
            {call.missed ? <small className="warning-text">capacity miss ×{call.missed}</small> : null}
          </article>
        )) : <span className="muted">No active hall calls.</span>}
      </div>
    </section>
  );
}

function MobileDecisionSummary({ snapshot, event }: { snapshot: Snapshot; event: SimulationEvent | null }) {
  const decision = snapshot.decision_tail.at(-1);
  return (
    <section className="mobile-decision-summary" aria-label="Selected event and decision reason">
      <div>
        <span>Selected event</span>
        <strong>{event ? `${event.kind.replaceAll("_", " ")} · T+${event.sim_time.toFixed(1)}s` : "Latest dispatch state"}</strong>
        <small>{event ? `${event.floor ?? "—"}F · ${event.elevator_id ?? "—"}` : `${snapshot.calls.length} active calls`}</small>
      </div>
      <div>
        <span>Decision reason</span>
        <strong>{decision?.chosen_elevator_id ?? "No decision yet"}</strong>
        <small>{decision?.reason ?? "Waiting for dispatch evidence."}</small>
      </div>
    </section>
  );
}

export function LiveOperations({ liveSnapshot, onSaveReplay, onControl, onInspectionSnapshotChange }: LiveOperationsProps) {
  const [replay, setReplay] = useState<ReplayPayload | null>(null);
  const [replayMode, setReplayMode] = useState(false);
  const [replayIndex, setReplayIndex] = useState(0);
  const [selectedEventSequence, setSelectedEventSequence] = useState<number | null>(null);
  const visibleSnapshot = replayMode && replay?.frames.length ? replay.frames[Math.min(replayIndex, replay.frames.length - 1)] : liveSnapshot;
  const selectedEvent = visibleSnapshot.event_tail.find((event) => event.sequence === selectedEventSequence) ?? decisionEvents(visibleSnapshot.event_tail)[0] ?? null;
  const replayHistory = replayMode && replay ? replay.frames.slice(0, replayIndex + 1).filter((frame) => frame.sim_time % 15 === 0).map((frame) => ({
    sim_time: frame.sim_time,
    avg_wait: frame.metrics.avg_wait,
    p95_wait: frame.metrics.p95_wait,
    avg_queue: frame.metrics.avg_queue,
  })) : visibleSnapshot.history;
  const waitSpec = useMemo<ChartSpec>(() => ({
    type: "timeSeries",
    title: "Wait trajectory",
    source: replayMode ? "saved replay frames" : "/api/snapshot history",
    x: "sim_time",
    y: ["avg_wait", "p95_wait"],
  }), [replayMode]);
  const heatmapSpec: ChartSpec = {
    type: "floorHeatmap",
    title: "Floor queue field",
    source: "/api/snapshot queues",
    metric: "current_queue",
  };

  useEffect(() => {
    onInspectionSnapshotChange?.(visibleSnapshot);
  }, [visibleSnapshot, onInspectionSnapshotChange]);

  async function saveReplay() {
    const saved = await onSaveReplay();
    setReplay(saved);
    setReplayIndex(Math.max(0, saved.frames.length - 1));
  }

  return (
    <div className="live-workbench">
      <div className="live-status-row">
        <div id="live-state" className={`live-state ${replayMode ? "replay" : liveSnapshot.running ? "live" : "paused"}`}><span>{replayMode ? "REPLAY MODE" : liveSnapshot.running ? "LIVE SIMULATION" : "PAUSED"}</span></div>
        <strong id="clock">{visibleSnapshot.clock}</strong>
        <span id="elapsed">T+{Math.floor(visibleSnapshot.sim_time / 60).toString().padStart(2, "0")}:{(visibleSnapshot.sim_time % 60).toString().padStart(2, "0")}</span>
        <span className="regime-readout">{visibleSnapshot.scenario} / {visibleSnapshot.policy}</span>
      </div>

      <div className="live-grid">
        <DigitalTwin snapshot={visibleSnapshot} />
        <div className="live-side-stack">
          <ActiveCalls snapshot={visibleSnapshot} />
          <EventStream events={visibleSnapshot.event_tail} selectedSequence={selectedEvent?.sequence ?? null} onSelect={(event) => setSelectedEventSequence(event.sequence)} />
        </div>
      </div>

      <MobileDecisionSummary snapshot={visibleSnapshot} event={selectedEvent} />

      <ReplayTimeline
        replay={replay}
        replayMode={replayMode}
        replayIndex={replayIndex}
        onReplayIndex={setReplayIndex}
        onSave={saveReplay}
        onEnter={() => { setReplayMode(true); setReplayIndex(0); }}
        onReturn={() => setReplayMode(false)}
      />

      <div className="metric-grid">
        <MetricCard label="Average wait" value={fmtSeconds(visibleSnapshot.metrics.avg_wait)} id="avg-wait" note="Passenger-level AWT" />
        <MetricCard label="P95 wait" value={fmtSeconds(visibleSnapshot.metrics.p95_wait)} id="p95-wait" note="Tail wait" />
        <MetricCard label="Waiting" value={String(visibleSnapshot.metrics.current_queue)} id="queue" note={`Lq avg ${visibleSnapshot.metrics.avg_queue.toFixed(2)}`} tone={visibleSnapshot.metrics.current_queue > 20 ? "warning" : "default"} />
        <MetricCard label="Capacity misses" value={String(visibleSnapshot.metrics.missed_capacity)} id="misses" note={`${visibleSnapshot.metrics.reassignments} predictive reassignments`} />
        <MetricCard label="Throughput" value={`${visibleSnapshot.metrics.served} served`} id="served" note={`${visibleSnapshot.metrics.arrivals} arrivals`} />
      </div>

      <div className="analytics-grid">
        <ChartRenderer spec={waitSpec} data={replayHistory} />
        <ChartRenderer spec={heatmapSpec} data={visibleSnapshot} />
        <section className="panel-card diagnostics-panel">
          <header className="section-heading"><div><span>Queueing diagnostic</span><strong>Little's Law check</strong></div></header>
          <dl className="diagnostic-list">
            <div><dt>Observed Lq</dt><dd id="lq-observed">{visibleSnapshot.metrics.avg_queue.toFixed(2)}</dd></div>
            <div><dt>λWq</dt><dd id="lq-derived">{visibleSnapshot.metrics.little_law_lq.toFixed(2)}</dd></div>
            <div><dt>Arrival rate</dt><dd id="arrival-rate">{visibleSnapshot.metrics.arrival_rate_per_min.toFixed(1)}/min</dd></div>
          </dl>
        </section>
      </div>
      <div id="queue-trend-chart" className="sr-only" aria-hidden="true"><span id="queue-trend-value">{Number(replayHistory.at(-1)?.avg_queue ?? 0).toFixed(2)}</span></div>
      <span id="reassignments" className="sr-only">{visibleSnapshot.metrics.reassignments} predictive reassignments</span>
      <span id="avg-queue" className="sr-only">Lq avg {visibleSnapshot.metrics.avg_queue.toFixed(2)}</span>
      {replayMode ? null : <span className="sr-only"><button type="button" onClick={() => onControl({ action: "step" })}>Step simulation</button></span>}
    </div>
  );
}
