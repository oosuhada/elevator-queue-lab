import type { PolicyName, ScenarioName, Snapshot } from "../../contracts/api";


interface LiveControlsProps {
  snapshot: Snapshot;
  disabled?: boolean;
  onControl: (payload: Record<string, unknown>) => Promise<void>;
}

export function LiveControls({ snapshot, disabled = false, onControl }: LiveControlsProps) {
  async function update(selectors: Partial<{ scenario: ScenarioName; policy: PolicyName; control_mode: string; speed: number }>) {
    await onControl({ action: "update", ...selectors });
  }

  return (
    <div className="live-controls" aria-label="Simulation controls">
      <label>
        Scenario
        <select id="scenario" disabled={disabled} value={snapshot.scenario} onChange={(event) => update({ scenario: event.target.value as ScenarioName })}>
          <option value="morning">Morning</option>
          <option value="lunch">Lunch</option>
          <option value="normal">Normal</option>
          <option value="evening">Evening</option>
          <option value="shock">Shock</option>
          <option value="mixed_day">Mixed day</option>
        </select>
      </label>
      <label>
        Policy
        <select id="policy" disabled={disabled} value={snapshot.policy} onChange={(event) => update({ policy: event.target.value as PolicyName })}>
          <option value="legacy_sticky">Legacy sticky</option>
          <option value="nearest_car">Nearest car</option>
          <option value="collective">Collective</option>
          <option value="queue_aware">Queue-aware</option>
          <option value="capr">CAPR</option>
        </select>
      </label>
      <label>
        Control
        <select id="control-mode" disabled={disabled} value={snapshot.simulation_config.control_mode} onChange={(event) => update({ control_mode: event.target.value })}>
          <option value="conventional">Conventional</option>
          <option value="destination">Destination</option>
        </select>
      </label>
      <label>
        Speed
        <select id="speed" disabled={disabled} value={String(snapshot.speed)} onChange={(event) => update({ speed: Number(event.target.value) })}>
          {[1, 5, 20, 60, 120].map((speed) => <option key={speed} value={speed}>{speed}×</option>)}
        </select>
      </label>
      <button id="pause" className="secondary-button" disabled={disabled} type="button" onClick={() => onControl({ action: snapshot.running ? "pause" : "start" })}>
        {snapshot.running ? "Pause" : "Resume"}
      </button>
      <button id="reset" className="secondary-button" disabled={disabled} type="button" onClick={() => onControl({ action: "reset" })}>
        Reset run
      </button>
    </div>
  );
}
