import { useState } from "react";
import type { DispatchDecision, Snapshot } from "../../contracts/api";


export function DispatchWorkbench({ snapshot }: { snapshot: Snapshot }) {
  const decisions = [...snapshot.decision_tail].reverse();
  const [selectedIndex, setSelectedIndex] = useState(0);
  const selected: DispatchDecision | undefined = decisions[selectedIndex] ?? decisions[0];
  return (
    <div className="dispatch-workbench" data-testid="dispatch-workbench">
      <section className="decision-list-pane panel-card">
        <header className="section-heading"><div><span>Decision ledger</span><strong>Retained dispatch evaluations</strong></div><span>{decisions.length} decisions</span></header>
        <div className="decision-list">{decisions.map((decision, index) => <button key={`${decision.sim_time}-${index}`} type="button" className={index === selectedIndex ? "is-active" : ""} onClick={() => setSelectedIndex(index)}><strong>T+{decision.sim_time.toFixed(1)} · {decision.floor}F {decision.direction > 0 ? "↑" : "↓"}</strong><span>{decision.chosen_elevator_id ?? "none"} · {decision.queue_size} queued</span></button>)}</div>
      </section>
      <section className="decision-analysis-pane panel-card">
        <header className="section-heading"><div><span>Candidate evaluation</span><strong>{selected ? selected.reason : "No decision yet"}</strong></div></header>
        {selected ? <div className="compact-table-wrap"><table className="compact-table"><caption>ETA, residual capacity, score and feasibility</caption><thead><tr><th>Car</th><th>ETA</th><th>Route</th><th>Projected load</th><th>Residual</th><th>Score</th><th>Feasible</th></tr></thead><tbody>{[...selected.candidates].sort((a, b) => a.score - b.score).map((candidate) => <tr key={candidate.elevator_id} className={candidate.elevator_id === selected.chosen_elevator_id ? "chosen" : ""}><td>{candidate.elevator_id}</td><td>{candidate.pickup_eta.toFixed(2)}s</td><td>{candidate.route_cost.toFixed(2)}s</td><td>{candidate.projected_load}</td><td>{candidate.residual_capacity}</td><td>{candidate.score.toFixed(2)}</td><td>{candidate.feasible ? "yes" : "no"}</td></tr>)}</tbody></table></div> : <p className="muted">No retained decision evidence.</p>}
      </section>
    </div>
  );
}
