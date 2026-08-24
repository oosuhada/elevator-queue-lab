import { useMemo, useState } from "react";
import { ChartRenderer } from "../../components/charts/ChartRenderer";
import { MetricCard } from "../../components/common/MetricCard";
import type { ReplayPayload, SimulationEvent, Snapshot } from "../../contracts/api";
import type { ChartSpec } from "../../contracts/chartSpec";
import { DigitalTwin } from "./DigitalTwin";


interface LiveOperationsProps {
  liveSnapshot: Snapshot;
  onSaveReplay: () => Promise<ReplayPayload>;
  onControl: (payload: Record<string, unknown>) => Promise<void>;
}

function fmtSeconds(value: number): string {
  return `${Number(value || 0).toFixed(1)}s`;
}

function EventStream({ events }: { events: SimulationEvent[] }) {
  const relevant = events.filter((event) => ["assign", "reassign", "assignment_invalidated", "full_pass"].includes(event.kind)).slice(-8).reverse();
  return (
    <section className="panel-card event-panel">
      <header className="section-heading"><div><span>Decision ledger</span><strong>Recent dispatch events</strong></div></header>
      <div id="event-stream" className="event-stream">
        {relevant.length ? relevant.map((event) => (
          <article key={event.sequence} className={`event event-${event.kind}`}>
            <time>T+{event.sim_time.toFixed(1)}s</time>
            <b>{event.kind.replaceAll("_", " ").toUpperCase()}</b>
            <span>{event.floor ?? "—"}F · {event.elevator_id ?? "—"}</span>
            {typeof event.details?.reason === "string" ? <small>{event.details.reason}</small> : null}
          </article>
        )) : <span className="muted">No dispatch events yet.</span>}
      </div>
    </section>
  );
}

function ActiveCalls({ snapshot }: { snapshot: Snapshot }) {
  const calls = [...snapshot.calls].sort((a, b) => b.wait - a.wait).slice(0, 12);
  return (
    <section className="panel-card calls-panel">
      <header className="section-heading"><div><span>Hall calls</span><strong>Active demand</strong></div><span>{snapshot.calls.length} calls</span></header>
      <div id="calls" className="call-list">
        {calls.length ? calls.map((call, index) => (
          <article key={`${call.floor}-${call.direction}-${call.destination}-${index}`} className="call" data-floor={call.floor} data-assigned={call.assigned ?? ""}>
            <strong>{call.floor}F {call.direction > 0 ? "↑" : "↓"}{call.destination ? ` → ${call.destination}F` : ""}</strong>
            <span>{call.assigned ?? "unassigned"}{call.assigned_score === null ? "" : ` · ${call.assigned_score.toFixed(1)}`}</span>
            <b className="wait">{call.wait.toFixed(0)}s</b>
            {call.missed ? <small className="warning-text">miss {call.missed}</small> : null}
          </article>
        )) : <span className="muted">No active hall calls.</span>}
      </div>
    </section>
  );
}

export function LiveOperations({ liveSnapshot, onSaveReplay, onControl }: LiveOperationsProps) {
  const [replay, setReplay] = useState<ReplayPayload | null>(null);
  const [replayMode, setReplayMode] = useState(false);
  const [replayIndex, setReplayIndex] = useState(0);
  const visibleSnapshot = replayMode && replay?.frames.length ? replay.frames[Math.min(replayIndex, replay.frames.length - 1)] : liveSnapshot;
  const replayHistory = replayMode && replay ? replay.frames.slice(0, replayIndex + 1).filter((frame) => frame.sim_time % 15 === 0).map((frame) => ({
    sim_time: frame.sim_time,
    avg_wait: frame.metrics.avg_wait,
    p95_wait: frame.metrics.p95_wait,
    avg_queue: frame.metrics.avg_queue,
  })) : visibleSnapshot.history;
  const waitSpec = useMemo<ChartSpec>(() => ({
    type: "timeSeries",
    title: "Wait trend",
    source: replayMode ? "saved replay frames" : "/api/snapshot history",
    x: "sim_time",
    y: ["avg_wait", "p95_wait"],
  }), [replayMode]);
  const heatmapSpec: ChartSpec = {
    type: "floorHeatmap",
    title: "Floor queue heatmap",
    source: "/api/snapshot queues",
    metric: "current_queue",
  };

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
      </div>
      <div className="metric-grid">
        <MetricCard label="Average wait" value={fmtSeconds(visibleSnapshot.metrics.avg_wait)} id="avg-wait" note="Passenger-level AWT" />
        <MetricCard label="P95 wait" value={fmtSeconds(visibleSnapshot.metrics.p95_wait)} id="p95-wait" note="Tail wait" />
        <MetricCard label="Waiting" value={String(visibleSnapshot.metrics.current_queue)} id="queue" note={`Lq avg ${visibleSnapshot.metrics.avg_queue.toFixed(2)}`} tone={visibleSnapshot.metrics.current_queue > 20 ? "warning" : "default"} />
        <MetricCard label="Capacity misses" value={String(visibleSnapshot.metrics.missed_capacity)} id="misses" note={`${visibleSnapshot.metrics.reassignments} predictive reassignments`} />
        <MetricCard label="Throughput" value={`${visibleSnapshot.metrics.served} served`} id="served" note={`${visibleSnapshot.metrics.arrivals} arrivals`} />
      </div>
      <div className="live-grid">
        <DigitalTwin snapshot={visibleSnapshot} />
        <div className="live-side-stack">
          <ActiveCalls snapshot={visibleSnapshot} />
          <EventStream events={visibleSnapshot.event_tail} />
        </div>
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
      <section className="panel-card replay-panel">
        <header className="section-heading"><div><span>Deterministic replay</span><strong>Inspect the same saved state</strong></div><span id="replay-status">{replay?.source === "saved_run" ? "saved run" : "not saved"}</span></header>
        <div className="replay-controls">
          <button id="save-replay" className="secondary-button" type="button" onClick={saveReplay}>Save replay</button>
          <button id="enter-replay" className="secondary-button" type="button" disabled={!replay} onClick={() => { setReplayMode(true); setReplayIndex(0); }}>Enter replay</button>
          <button id="return-live" className="secondary-button" type="button" disabled={!replayMode} onClick={() => setReplayMode(false)}>Return live</button>
          <input
            id="replay-slider"
            aria-label="Replay frame"
            type="range"
            min="0"
            max={Math.max(0, (replay?.frames.length ?? 1) - 1)}
            value={replayIndex}
            disabled={!replayMode || !replay}
            onInput={(event) => setReplayIndex(Number(event.currentTarget.value))}
            onChange={(event) => setReplayIndex(Number(event.currentTarget.value))}
          />
          <span id="replay-frame">{replay ? `Frame ${replayIndex + 1} / ${replay.frames.length}` : "Frame —"}</span>
        </div>
      </section>
      <div id="queue-trend-chart" className="sr-only" aria-hidden="true"><span id="queue-trend-value">{Number(replayHistory.at(-1)?.avg_queue ?? 0).toFixed(2)}</span></div>
      <span id="reassignments" className="sr-only">{visibleSnapshot.metrics.reassignments} predictive reassignments</span>
      <span id="avg-queue" className="sr-only">Lq avg {visibleSnapshot.metrics.avg_queue.toFixed(2)}</span>
      {replayMode ? null : <span className="sr-only"><button type="button" onClick={() => onControl({ action: "step" })}>Step simulation</button></span>}
    </div>
  );
}
