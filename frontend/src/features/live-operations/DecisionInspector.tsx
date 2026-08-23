import { motion, useReducedMotion } from "motion/react";
import { Inspector } from "../../components/shell/Inspector";
import type { CandidateEvaluation, DispatchDecision, Snapshot } from "../../contracts/api";


const TERM_LABELS: Record<string, string> = {
  eta: "ETA",
  route: "Route",
  load: "Load",
  direction: "Direction",
  capacity_guard: "Capacity guard",
  capacity_shortfall: "Queue shortfall",
  age_credit: "Age credit",
  feasibility_guard: "Infeasible guard",
};

function candidateGate(candidate: CandidateEvaluation, decision: DispatchDecision): string {
  if (!decision.current_assignment) return "initial assignment";
  if (candidate.elevator_id === decision.current_assignment) return "incumbent";
  if (candidate.elevator_id === decision.chosen_elevator_id) return "replacement candidate";
  return "not selected";
}

function ScoreDecomposition({ candidate, maxMagnitude }: { candidate: CandidateEvaluation; maxMagnitude: number }) {
  const reducedMotion = useReducedMotion();
  const terms = Object.entries(candidate.score_terms ?? {}).filter(([, value]) => Number.isFinite(value));
  return (
    <div className="score-decomposition" aria-label={`${candidate.elevator_id} score decomposition`}>
      {terms.map(([key, raw]) => {
        const value = Number(raw);
        const magnitude = Math.min(100, (Math.abs(value) / Math.max(1, maxMagnitude)) * 100);
        return (
          <div className={`score-term ${value < 0 ? "is-credit" : ""}`} key={key}>
            <span>{TERM_LABELS[key] ?? key}</span>
            <div><motion.i initial={false} animate={{ width: `${magnitude}%` }} transition={{ duration: reducedMotion ? 0 : 0.22 }} /></div>
            <strong>{value >= 0 ? "+" : ""}{value.toFixed(1)}</strong>
          </div>
        );
      })}
    </div>
  );
}

export function DecisionInspector({ decision, snapshot }: { decision?: DispatchDecision; snapshot: Snapshot }) {
  if (!decision) {
    return (
      <Inspector title="Dispatch decision" subtitle="Waiting for evidence">
        <p id="decision-reason" className="muted">Waiting for the first dispatch decision…</p>
      </Inspector>
    );
  }
  const rows = [...(decision.candidates ?? [])].sort((a, b) => Number(a.score) - Number(b.score));
  const chosen = rows.find((candidate) => candidate.elevator_id === decision.chosen_elevator_id);
  const incumbent = rows.find((candidate) => candidate.elevator_id === decision.current_assignment);
  const maxTermMagnitude = Math.max(1, ...rows.flatMap((candidate) => Object.values(candidate.score_terms ?? {}).map((value) => Math.abs(Number(value)))));
  const scoreGain = incumbent && chosen && incumbent.elevator_id !== chosen.elevator_id ? incumbent.score - chosen.score : null;
  const etaGain = incumbent && chosen && incumbent.elevator_id !== chosen.elevator_id ? incumbent.pickup_eta - chosen.pickup_eta : null;
  return (
    <Inspector title="Dispatch decision" subtitle={`T+${decision.sim_time.toFixed(1)}s · ${decision.bank} bank`}>
      <div className="decision-callout">
        <span>Call under evaluation</span>
        <strong id="decision-call">{decision.floor}F {decision.direction > 0 ? "↑" : "↓"}{decision.destination ? ` → ${decision.destination}F` : ""}</strong>
        <small id="decision-queue">queue {decision.queue_size} · selected {decision.chosen_elevator_id ?? "none"}</small>
      </div>
      <p id="decision-reason" className="decision-reason">{decision.reason}</p>

      <section className="reassignment-gate" aria-label="Reassignment gate">
        <header><span>Reassignment gate</span><strong>{decision.current_assignment ? `${decision.current_assignment} incumbent` : "initial assignment"}</strong></header>
        <div className="gate-grid">
          <div><span>Score gain</span><strong>{scoreGain === null ? "—" : `${scoreGain.toFixed(1)} / ≥${snapshot.simulation_config.reassignment_min_gain.toFixed(1)}`}</strong></div>
          <div><span>ETA gain</span><strong>{etaGain === null ? "—" : `${etaGain.toFixed(1)}s / ≥${snapshot.simulation_config.reassignment_min_eta_gain_seconds.toFixed(1)}s`}</strong></div>
          <div><span>Cooldown</span><strong>{snapshot.simulation_config.reassignment_cooldown_seconds.toFixed(1)}s</strong></div>
          <div><span>Penalty model</span><strong>gate, not score term</strong></div>
        </div>
        <p>No numeric reassignment penalty is fabricated here: CAPR applies cooldown, score-gain, ETA-gain and budget gates after candidate scoring.</p>
      </section>

      <div className="candidate-stack">
        {rows.map((candidate) => (
          <article key={candidate.elevator_id} className={`candidate-instrument ${candidate.elevator_id === decision.chosen_elevator_id ? "is-chosen" : ""} ${candidate.feasible ? "" : "is-infeasible"}`}>
            <header>
              <div><span>{candidateGate(candidate, decision)}</span><strong>{candidate.elevator_id}{candidate.elevator_id === decision.chosen_elevator_id ? " / CHOSEN" : ""}</strong></div>
              <b>{candidate.score.toFixed(1)}</b>
            </header>
            <div className="candidate-route-readout">
              <span><small>ETA</small><strong>{candidate.pickup_eta.toFixed(1)}s</strong></span>
              <span><small>Route cost</small><strong>{candidate.route_cost.toFixed(1)}s</strong></span>
              <span><small>Pred. capacity</small><strong>{candidate.residual_capacity}</strong></span>
              <span><small>Age</small><strong>{Number(candidate.age_seconds ?? 0).toFixed(1)}s</strong></span>
            </div>
            <ScoreDecomposition candidate={candidate} maxMagnitude={maxTermMagnitude} />
            <p>{candidate.reason}</p>
          </article>
        ))}
      </div>

      <div className="compact-table-wrap decision-raw-table">
        <table className="compact-table">
          <caption>Recorded candidate values</caption>
          <thead><tr><th>Car</th><th>ETA</th><th>Residual</th><th>Route</th><th>Age credit</th><th>Score</th><th>Gate role</th></tr></thead>
          <tbody id="decision-candidates">
            {rows.map((candidate) => (
              <tr key={candidate.elevator_id} className={candidate.elevator_id === decision.chosen_elevator_id ? "chosen" : ""}>
                <td>{candidate.elevator_id}{candidate.elevator_id === decision.chosen_elevator_id ? " ✓" : ""}</td>
                <td>{candidate.pickup_eta.toFixed(1)}s</td>
                <td>{candidate.residual_capacity}</td>
                <td>{candidate.route_cost.toFixed(1)}s</td>
                <td>{Number(candidate.score_terms?.age_credit ?? 0).toFixed(1)}</td>
                <td>{candidate.score.toFixed(1)}</td>
                <td>{candidateGate(candidate, decision)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Inspector>
  );
}
