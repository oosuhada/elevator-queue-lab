import type { DispatchDecision } from "../../contracts/api";
import { Inspector } from "../../components/shell/Inspector";


export function DecisionInspector({ decision }: { decision?: DispatchDecision }) {
  if (!decision) {
    return (
      <Inspector title="Dispatch decision" subtitle="Waiting for evidence">
        <p id="decision-reason" className="muted">Waiting for the first dispatch decision…</p>
      </Inspector>
    );
  }
  const rows = [...(decision.candidates ?? [])].sort((a, b) => Number(a.score) - Number(b.score));
  return (
    <Inspector title="Dispatch decision" subtitle={`T+${decision.sim_time.toFixed(1)}s · ${decision.bank} bank`}>
      <div className="inspector-kv">
        <span>Call</span><strong id="decision-call">{decision.floor}F {decision.direction > 0 ? "↑" : "↓"}{decision.destination ? ` → ${decision.destination}F` : ""}</strong>
        <span>Queue</span><strong id="decision-queue">queue {decision.queue_size}</strong>
        <span>Selected</span><strong>{decision.chosen_elevator_id ?? "none"}</strong>
      </div>
      <p id="decision-reason" className="decision-reason">{decision.reason}</p>
      <div className="compact-table-wrap">
        <table className="compact-table">
          <caption>Candidate evaluation</caption>
          <thead><tr><th>Car</th><th>ETA</th><th>Residual</th><th>Score</th><th>Feasible</th></tr></thead>
          <tbody id="decision-candidates">
            {rows.map((candidate) => (
              <tr key={candidate.elevator_id} className={candidate.elevator_id === decision.chosen_elevator_id ? "chosen" : ""}>
                <td>{candidate.elevator_id}{candidate.elevator_id === decision.chosen_elevator_id ? " ✓" : ""}</td>
                <td>{candidate.pickup_eta.toFixed(1)}s</td>
                <td>{candidate.residual_capacity}</td>
                <td>{candidate.score.toFixed(1)}</td>
                <td>{candidate.feasible ? "yes" : "no"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Inspector>
  );
}
