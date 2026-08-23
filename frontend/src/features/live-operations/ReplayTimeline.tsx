import { scaleLinear } from "d3-scale";
import { motion, useReducedMotion } from "motion/react";
import { useMemo } from "react";
import type { ReplayPayload, SimulationEvent, Snapshot } from "../../contracts/api";


interface TimelineMarker {
  id: string;
  frameIndex: number;
  time: number;
  kind: "reassign" | "full-pass" | "policy" | "wait-spike" | "decision";
  label: string;
}

function nearestFrame(frames: Snapshot[], simTime: number): number {
  let best = 0;
  let bestDistance = Number.POSITIVE_INFINITY;
  frames.forEach((frame, index) => {
    const distance = Math.abs(frame.sim_time - simTime);
    if (distance < bestDistance) {
      best = index;
      bestDistance = distance;
    }
  });
  return best;
}

function replayMarkers(replay: ReplayPayload): TimelineMarker[] {
  const markers: TimelineMarker[] = [];
  const seenEvents = new Set<number>();
  let priorPolicy: string | null = null;
  let priorP95: number | null = null;
  replay.frames.forEach((frame, frameIndex) => {
    if (frame.policy !== priorPolicy) {
      markers.push({ id: `policy-${frameIndex}`, frameIndex, time: frame.sim_time, kind: "policy", label: `Policy ${frame.policy}` });
      priorPolicy = frame.policy;
    }
    if (priorP95 !== null) {
      const delta = frame.metrics.p95_wait - priorP95;
      if (delta >= Math.max(4, priorP95 * 0.18)) {
        markers.push({ id: `spike-${frameIndex}`, frameIndex, time: frame.sim_time, kind: "wait-spike", label: `P95 wait spike +${delta.toFixed(1)}s` });
      }
    }
    priorP95 = frame.metrics.p95_wait;
    frame.event_tail.forEach((event: SimulationEvent) => {
      if (seenEvents.has(event.sequence)) return;
      seenEvents.add(event.sequence);
      if (event.kind === "reassign") {
        markers.push({ id: `event-${event.sequence}`, frameIndex: nearestFrame(replay.frames, event.sim_time), time: event.sim_time, kind: "reassign", label: `Reassign ${event.floor ?? "—"}F → ${event.elevator_id ?? "—"}` });
      }
      if (event.kind === "full_pass") {
        markers.push({ id: `event-${event.sequence}`, frameIndex: nearestFrame(replay.frames, event.sim_time), time: event.sim_time, kind: "full-pass", label: `Full pass ${event.floor ?? "—"}F · ${event.elevator_id ?? "—"}` });
      }
    });
  });
  const current = replay.frames.at(-1)?.decision_tail.at(-1);
  if (current) {
    markers.push({
      id: "latest-decision",
      frameIndex: nearestFrame(replay.frames, current.sim_time),
      time: current.sim_time,
      kind: "decision",
      label: `Decision ${current.floor}F → ${current.chosen_elevator_id ?? "none"}`,
    });
  }
  return markers.sort((a, b) => a.time - b.time || a.kind.localeCompare(b.kind));
}

interface ReplayTimelineProps {
  replay: ReplayPayload | null;
  replayMode: boolean;
  replayIndex: number;
  onReplayIndex: (index: number) => void;
  onSave: () => Promise<void>;
  onEnter: () => void;
  onReturn: () => void;
}

export function ReplayTimeline({ replay, replayMode, replayIndex, onReplayIndex, onSave, onEnter, onReturn }: ReplayTimelineProps) {
  const reducedMotion = useReducedMotion();
  const markers = useMemo(() => replay ? replayMarkers(replay) : [], [replay]);
  const frameCount = replay?.frames.length ?? 1;
  const scale = useMemo(() => scaleLinear().domain([0, Math.max(1, frameCount - 1)]).range([0, 100]), [frameCount]);
  const currentFrame = replay?.frames[Math.min(replayIndex, frameCount - 1)];
  return (
    <section className="replay-panel physical-timeline" aria-label="Deterministic replay timeline">
      <header className="section-heading">
        <div><span>Physical timeline</span><strong>Deterministic replay instrument</strong></div>
        <span id="replay-status">{replay?.source === "saved_run" ? "saved run" : "not saved"}</span>
      </header>
      <div className="timeline-actions">
        <button id="save-replay" className="secondary-button" type="button" onClick={() => void onSave()}>Save run</button>
        <button id="enter-replay" className="secondary-button" type="button" disabled={!replay} onClick={onEnter}>Replay from start</button>
        <button id="return-live" className="secondary-button" type="button" disabled={!replayMode} onClick={onReturn}>Return live</button>
        <span id="replay-frame">{replay ? `Frame ${replayIndex + 1} / ${replay.frames.length}` : "Frame —"}</span>
        {currentFrame ? <strong>T+{currentFrame.sim_time.toFixed(1)}s</strong> : null}
      </div>
      <div className="timeline-track-wrap">
        <div className="timeline-ruler" aria-hidden="true">
          {Array.from({ length: 13 }, (_, index) => <span key={index} style={{ left: `${(index / 12) * 100}%` }} />)}
        </div>
        <div className="timeline-markers" aria-label="Replay event markers">
          {markers.map((marker) => (
            <button
              key={marker.id}
              type="button"
              className={`timeline-marker marker-${marker.kind}`}
              style={{ left: `${scale(marker.frameIndex)}%` }}
              title={`T+${marker.time.toFixed(1)}s · ${marker.label}`}
              aria-label={`T+${marker.time.toFixed(1)} seconds, ${marker.label}`}
              disabled={!replayMode}
              onClick={() => onReplayIndex(marker.frameIndex)}
            >
              <span aria-hidden="true" />
            </button>
          ))}
          <motion.div
            className="timeline-playhead"
            initial={false}
            animate={{ left: `${scale(replayIndex)}%` }}
            transition={{ duration: reducedMotion ? 0 : 0.16, ease: "easeOut" }}
            aria-hidden="true"
          />
        </div>
        <input
          id="replay-slider"
          aria-label="Replay frame"
          type="range"
          min="0"
          max={Math.max(0, frameCount - 1)}
          value={replayIndex}
          disabled={!replayMode || !replay}
          onInput={(event) => onReplayIndex(Number(event.currentTarget.value))}
          onChange={(event) => onReplayIndex(Number(event.currentTarget.value))}
        />
      </div>
      <div className="timeline-legend" aria-label="Timeline marker legend">
        <span className="legend-reassign">Reassignment</span>
        <span className="legend-full-pass">Full pass</span>
        <span className="legend-policy">Policy</span>
        <span className="legend-wait-spike">Wait spike</span>
        <span className="legend-decision">Selected decision</span>
      </div>
    </section>
  );
}
