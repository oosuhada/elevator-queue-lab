import { motion, useReducedMotion } from "motion/react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import type { HallCallSnapshot, Snapshot } from "../../contracts/api";
import { useVisualCapability } from "../../hooks/useVisualCapability";


const FLOOR_COUNT = 18;
const CAR_ORDER = ["L1", "L2", "L3", "H1", "H2", "H3"];
const DepthTwinPrototype = lazy(() => import("./DepthTwinPrototype").then((module) => ({ default: module.DepthTwinPrototype })));

function floorPercent(floor: number): number {
  return ((floor - 1) / (FLOOR_COUNT - 1)) * 100;
}

function callLabel(call: HallCallSnapshot): string {
  const destination = call.destination ? ` → ${call.destination}F` : "";
  return `${call.floor}F ${call.direction > 0 ? "↑" : "↓"}${destination}`;
}

function eventKey(floor: number | null, elevatorId: string | null): string {
  return `${floor ?? ""}:${elevatorId ?? ""}`;
}

export function DigitalTwin({ snapshot }: { snapshot: Snapshot }) {
  const [view, setView] = useState<"section" | "depth">("section");
  const [focusMode, setFocusMode] = useState(false);
  const [compactViewport, setCompactViewport] = useState(false);
  const capability = useVisualCapability();
  const reducedMotion = useReducedMotion();
  const assignmentCalls = snapshot.calls.filter((call) => call.assigned).slice(0, 16);
  const recentReassignments = useMemo(() => new Set(snapshot.event_tail.filter((event) => event.kind === "reassign").map((event) => eventKey(event.floor, event.elevator_id))), [snapshot.event_tail]);
  const invalidatedFloors = useMemo(() => new Set(snapshot.event_tail.filter((event) => event.kind === "assignment_invalidated").map((event) => event.floor).filter((floor): floor is number => typeof floor === "number")), [snapshot.event_tail]);
  const fullPassFloors = useMemo(() => new Set(snapshot.event_tail.filter((event) => event.kind === "full_pass").map((event) => event.floor).filter((floor): floor is number => typeof floor === "number")), [snapshot.event_tail]);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") {
      setCompactViewport(false);
      return undefined;
    }
    const query = window.matchMedia("(max-width: 899px)");
    const update = () => setCompactViewport(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  const depthAvailable = capability.webgl && !capability.lowPower && !compactViewport;
  const activeView = view === "depth" && depthAvailable ? "depth" : "section";
  return (
    <section className={`digital-twin-card architectural-twin ${focusMode ? "focus-mode" : ""}`} aria-label="18-floor six-car digital twin">
      <header className="section-heading twin-heading">
        <div>
          <span>Architectural section · live state</span>
          <strong>18F vertical traffic laboratory</strong>
          <small>{snapshot.scenario} regime · {snapshot.policy.toUpperCase()} · T+{snapshot.sim_time.toFixed(1)}s</small>
        </div>
        <div className="twin-toolbar">
          <div className="view-switch" role="group" aria-label="Building visualization mode">
            <button type="button" className={activeView === "section" ? "is-active" : ""} onClick={() => setView("section")}>Section</button>
            <button type="button" className={activeView === "depth" ? "is-active" : ""} disabled={!depthAvailable} title={depthAvailable ? "Open 2.5D state prototype" : compactViewport ? "2.5D study is desktop-only" : capability.reason ?? "2.5D unavailable"} onClick={() => setView("depth")}>2.5D study</button>
          </div>
          <button type="button" className="focus-button" onClick={() => setFocusMode((value) => !value)}>{focusMode ? "Exit focus" : "Focus"}</button>
        </div>
      </header>
      <div className="twin-legend" aria-label="Elevator state legend">
        <span className="legend-low">Low zone · 1–9F</span>
        <span className="legend-high">High zone · 1, 10–18F</span>
        <span className="legend-reassign">Reassigned</span>
        <span className="legend-full-pass">Full pass</span>
        <span className="legend-stale">Invalidated assignment</span>
      </div>
      {activeView === "depth" ? (
        <Suspense fallback={<div className="depth-prototype depth-loading"><span>Loading 2.5D study…</span></div>}>
          <DepthTwinPrototype snapshot={snapshot} />
        </Suspense>
      ) : (
        <div id="building" className="building sectional-building" data-render-mode="svg-css-section">
          <div className="zone-field zone-field-high" aria-hidden="true"><span>HIGH BANK / 10–18</span></div>
          <div className="zone-field zone-field-low" aria-hidden="true"><span>LOW BANK / 2–9</span></div>
          <div className="lobby-band" aria-hidden="true"><span>1F SHARED LOBBY</span></div>
          <div id="floor-labels" className="floor-labels" aria-hidden="true">
            {Array.from({ length: FLOOR_COUNT }, (_, index) => index + 1).map((floor) => (
              <span key={floor} style={{ bottom: `calc(${floorPercent(floor)}% - 7px)` }}>
                {floor === FLOOR_COUNT ? "18F / ROOF" : `${floor.toString().padStart(2, "0")}F`}
              </span>
            ))}
          </div>
          <div id="floors" className="floors">
            {Array.from({ length: FLOOR_COUNT }, (_, index) => index + 1).map((floor) => {
              const queue = snapshot.queues[String(floor)] ?? { up: 0, down: 0 };
              const total = Number(queue.up) + Number(queue.down);
              const status = invalidatedFloors.has(floor) ? "stale" : fullPassFloors.has(floor) ? "full-pass" : total > 0 ? "queued" : "clear";
              return (
                <div key={floor}>
                  <span className={`floor-line ${floor === 1 ? "lobby" : ""}`} data-floor={floor} style={{ bottom: `${floorPercent(floor)}%` }} />
                  {total > 0 || status !== "clear" ? (
                    <span className={`queue-badge queue-${status}`} data-floor={floor} style={{ bottom: `calc(${floorPercent(floor)}% - 9px)` }} title={`${floor}F queue: up ${queue.up}, down ${queue.down}; state ${status}`}>
                      <b>↑{queue.up}</b><b>↓{queue.down}</b><i aria-hidden="true" />
                    </span>
                  ) : null}
                </div>
              );
            })}
          </div>
          <div id="shafts" className="shafts">
            {CAR_ORDER.map((carId, index) => {
              const car = snapshot.elevators.find((item) => item.id === carId);
              if (!car) return null;
              const arrow = car.direction > 0 ? "↑" : car.direction < 0 ? "↓" : "·";
              const carBottom = `calc(${floorPercent(car.floor)}% - 17px)`;
              return (
                <div key={carId} className={`shaft ${car.bank}`} data-id={carId}>
                  <span className="shaft-index">{index + 1}</span>
                  <span className="shaft-name">{carId}</span>
                  <motion.div
                    className={`car ${car.bank} ${car.load >= car.capacity ? "full" : ""} ${car.door_open ? "door-open" : ""}`}
                    data-car-id={car.id}
                    data-floor={String(car.floor)}
                    data-load={String(car.load)}
                    data-capacity={String(car.capacity)}
                    data-phase={String(car.phase)}
                    initial={false}
                    animate={{ bottom: carBottom }}
                    transition={{ duration: reducedMotion ? 0 : 0.26, ease: "linear" }}
                    title={`${car.id}: floor ${car.floor}, ${car.phase}, route ${car.stops.join(", ") || "none"}`}
                  >
                    <span className="car-direction">{arrow}</span>
                    <strong>{car.id}</strong>
                    <span className="car-load">{car.load}/{car.capacity}</span>
                    <span className="car-door" aria-hidden="true"><i /><i /></span>
                  </motion.div>
                </div>
              );
            })}
          </div>
          <svg id="assignment-overlay" className="assignment-overlay" viewBox="0 0 1000 720" preserveAspectRatio="none" aria-label="Active assignment links">
            {assignmentCalls.map((call, index) => {
              const carIndex = Math.max(0, CAR_ORDER.indexOf(call.assigned ?? ""));
              const y = 690 - floorPercent(call.floor) * 6.5;
              const x2 = 330 + carIndex * 100;
              const isReassign = recentReassignments.has(eventKey(call.floor, call.assigned));
              const isStale = invalidatedFloors.has(call.floor);
              return (
                <g key={`${call.floor}-${call.direction}-${call.bank}-${index}`}>
                  <line
                    x1="210"
                    y1={y}
                    x2={x2}
                    y2={y}
                    className={`${call.bank === "low" ? "link-low" : "link-high"} ${isReassign ? "link-reassign" : ""} ${isStale ? "link-stale" : ""}`}
                  />
                  <title>{`${callLabel(call)} assigned to ${call.assigned}`}</title>
                </g>
              );
            })}
          </svg>
          <div className="section-titleblock" aria-hidden="true">
            <span>EQL / SECTION A-A</span><strong>6 SHAFT GROUP CONTROL</strong><small>state scale: simulator floor coordinate</small>
          </div>
        </div>
      )}
      {!depthAvailable ? <p className="capability-note">2.5D study disabled: {compactViewport ? "compact viewport" : capability.reason ?? "capability check"}. The authoritative 2D section remains fully available.</p> : null}
    </section>
  );
}
