import type { HallCallSnapshot, Snapshot } from "../../contracts/api";


const FLOOR_COUNT = 18;
const CAR_ORDER = ["L1", "L2", "L3", "H1", "H2", "H3"];

function floorPercent(floor: number): number {
  return ((floor - 1) / (FLOOR_COUNT - 1)) * 100;
}

function callLabel(call: HallCallSnapshot): string {
  const destination = call.destination ? ` → ${call.destination}F` : "";
  return `${call.floor}F ${call.direction > 0 ? "↑" : "↓"}${destination}`;
}

export function DigitalTwin({ snapshot }: { snapshot: Snapshot }) {
  const assignmentCalls = snapshot.calls.filter((call) => call.assigned).slice(0, 16);
  return (
    <section className="digital-twin-card" aria-label="18-floor six-car digital twin">
      <header className="section-heading">
        <div>
          <span>Digital Twin</span>
          <strong>18 floors · 6 cars</strong>
        </div>
        <div className="twin-legend" aria-label="Elevator bank legend">
          <span className="legend-low">Low bank</span>
          <span className="legend-high">High bank</span>
        </div>
      </header>
      <div id="building" className="building">
        <div id="floor-labels" className="floor-labels" aria-hidden="true">
          {Array.from({ length: FLOOR_COUNT }, (_, index) => index + 1).map((floor) => (
            <span key={floor} style={{ bottom: `calc(${floorPercent(floor)}% - 7px)` }}>
              {floor === FLOOR_COUNT ? "18F · ROOF" : `${floor}F`}
            </span>
          ))}
        </div>
        <div id="floors" className="floors">
          {Array.from({ length: FLOOR_COUNT }, (_, index) => index + 1).map((floor) => {
            const queue = snapshot.queues[String(floor)] ?? { up: 0, down: 0 };
            const total = Number(queue.up) + Number(queue.down);
            return (
              <div key={floor}>
                <span
                  className={`floor-line ${floor === 1 ? "lobby" : ""}`}
                  data-floor={floor}
                  style={{ bottom: `${floorPercent(floor)}%` }}
                />
                {total > 0 ? (
                  <span className="queue-badge" data-floor={floor} style={{ bottom: `calc(${floorPercent(floor)}% - 9px)` }}>
                    <b>↑ {queue.up}</b><b>↓ {queue.down}</b>
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>
        <div id="shafts" className="shafts">
          {CAR_ORDER.map((carId) => {
            const car = snapshot.elevators.find((item) => item.id === carId);
            if (!car) return null;
            const arrow = car.direction > 0 ? "↑" : car.direction < 0 ? "↓" : "·";
            return (
              <div key={carId} className={`shaft ${car.bank}`} data-id={carId}>
                <div
                  className={`car ${car.bank} ${car.load >= car.capacity ? "full" : ""} ${car.door_open ? "door-open" : ""}`}
                  data-car-id={car.id}
                  data-floor={String(car.floor)}
                  data-load={String(car.load)}
                  data-capacity={String(car.capacity)}
                  data-phase={String(car.phase)}
                  style={{ bottom: `calc(${floorPercent(car.floor)}% - 16px)` }}
                  title={`${car.id}: floor ${car.floor}, ${car.phase}, route ${car.stops.join(", ") || "none"}`}
                >
                  <strong>{car.id} {arrow}</strong>
                  <span>{car.load}/{car.capacity}</span>
                </div>
              </div>
            );
          })}
        </div>
        <svg id="assignment-overlay" className="assignment-overlay" viewBox="0 0 1000 720" preserveAspectRatio="none" aria-label="Active assignment links">
          {assignmentCalls.map((call, index) => {
            const carIndex = Math.max(0, CAR_ORDER.indexOf(call.assigned ?? ""));
            const y = 690 - floorPercent(call.floor) * 6.5;
            const x2 = 330 + carIndex * 100;
            return (
              <line
                key={`${call.floor}-${call.direction}-${call.bank}-${index}`}
                x1="210"
                y1={y}
                x2={x2}
                y2={y}
                className={call.bank === "low" ? "link-low" : "link-high"}
              />
            );
          })}
        </svg>
      </div>
    </section>
  );
}
