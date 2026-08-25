import { DataPill } from "../../components/common/DataPill";
import type { TheoryPayload } from "../../contracts/api";


function scale(value: number, min: number, max: number, start: number, end: number): number {
  if (max === min) return (start + end) / 2;
  return start + ((value - min) / (max - min)) * (end - start);
}

export function TheoryWorkbench({ payload }: { payload: TheoryPayload }) {
  const discovery = payload.discovery as any;
  const validation = payload.validation as any;
  const theory = discovery.theory;
  const result = validation.result;
  const threshold = Number(validation.frozen_discovery_threshold?.threshold ?? theory.best_single_threshold.threshold);
  const cells = [
    ...discovery.cells.map((cell: any) => ({ ...cell, kind: "discovery" })),
    ...validation.cells.map((cell: any) => ({ ...cell, kind: "validation" })),
  ];
  const xs = cells.map((cell: any) => Number(cell.demand.bidirectional_load_rate));
  const ys = cells.map((cell: any) => Number(cell.capr_vs_static.metrics.avg_wait.delta_mean));
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const gated = result.gated_policy_projection;

  return (
    <div className="analysis-workbench theory-workbench" data-testid="theory-workbench">
      <section id="theory-takeaway" className="theory-takeaway">
        <span>Counterflow Criticality · M7</span>
        <div className="theory-takeaway-copy">
          <strong>Congestion alone is not the trigger.</strong>
          <p>Continuous predictive reassignment becomes valuable when traffic intensity and counterflow rise together.</p>
          <small>This is a synthetic-system empirical rule with a fuzzy threshold, not a universal theorem.</small>
        </div>
      </section>
      <section id="theory-leaders" className="evidence-detail-grid theory-leaders">
        <article className="theory-leader"><span>Candidate load index</span><strong>B = λ × 4p↑(1-p↑)</strong></article>
        <article className="theory-leader"><span>Frozen threshold</span><strong>B ≥ {threshold.toFixed(2)}</strong></article>
        <article className="theory-leader"><span>Held-out accuracy</span><strong>{(Number(result.accuracy) * 100).toFixed(1)}%</strong></article>
        <article className="theory-leader"><span>Held-out effect correlation</span><strong>{Number(result.frozen_linear_effect_model.correlation_observed_vs_predicted).toFixed(3)}</strong></article>
      </section>
      <div className="chart-grid-two">
        <article className="chart-frame">
          <header><strong>Discovery + held-out validation</strong><span>committed M7 evidence</span></header>
          <div className="chart-canvas">
            <svg id="theory-scatter" className="semantic-chart" viewBox="0 0 640 300" role="img" aria-label="Counterflow criticality effect scatter">
              <line x1="52" x2="616" y1={scale(0, minY, maxY, 260, 30)} y2={scale(0, minY, maxY, 260, 30)} className="chart-axis" />
              <line x1={scale(threshold, minX, maxX, 52, 616)} x2={scale(threshold, minX, maxX, 52, 616)} y1="26" y2="262" className="threshold-line" />
              {cells.map((cell: any, index: number) => (
                <circle
                  key={`${cell.kind}-${index}`}
                  data-kind={cell.kind}
                  cx={scale(Number(cell.demand.bidirectional_load_rate), minX, maxX, 52, 616)}
                  cy={scale(Number(cell.capr_vs_static.metrics.avg_wait.delta_mean), minY, maxY, 260, 30)}
                  r={cell.kind === "validation" ? 5 : 4}
                  className={cell.kind === "validation" ? "theory-point validation" : "theory-point discovery"}
                />
              ))}
              <text x="245" y="292">B · bidirectional load rate</text>
            </svg>
          </div>
        </article>
        <section className="panel-card theory-evidence-panel">
          <header className="section-heading"><div><span>Falsification result</span><strong>Frozen discovery rule on held-out grid</strong></div></header>
          <dl className="diagnostic-list">
            <div><dt>Precision</dt><dd>{Number(result.precision).toFixed(2)}</dd></div>
            <div><dt>Recall</dt><dd>{Number(result.recall).toFixed(2)}</dd></div>
            <div><dt>Effect MAE</dt><dd>{Number(result.frozen_linear_effect_model.mae_seconds).toFixed(3)}s</dd></div>
            <div><dt>Effect RMSE</dt><dd>{Number(result.frozen_linear_effect_model.rmse_seconds).toFixed(3)}s</dd></div>
            <div><dt>Energy overhead reduction</dt><dd>{(Number(gated.energy_overhead_reduction_vs_always_on_capr) * 100).toFixed(1)}%</dd></div>
            <div><dt>Wait gain retained</dt><dd>{(Number(gated.wait_gain_retained_vs_always_on_capr) * 100).toFixed(1)}%</dd></div>
          </dl>
          <div id="theory-rule" className="theory-rule"><strong>Fit slope {Number(theory.linear_wait_delta_fit.slope_seconds_per_bidirectional_pax_per_min).toFixed(3)} s per B-unit</strong><span>Discovery r² {Number(theory.linear_wait_delta_fit.r_squared).toFixed(3)}</span></div>
          <p id="theory-caveat" className="evidence-note">The held-out accuracy is {Number(result.accuracy).toFixed(3)}, with false positives and a fuzzy phase transition. The threshold is useful as a falsifiable operating hypothesis, not a hard physical law.</p>
        </section>
      </div>
      <section id="canonical-theory-row" className="canonical-theory-row">
        {theory.phase_bins.map((phase: any, index: number) => <article key={index}><span>B phase {phase.lower}–{phase.upper ?? "∞"}</span><strong>{Number(phase.mean_avg_wait_delta_seconds).toFixed(2)}s Δ AWT</strong><small>{phase.clean_gain_cells}/{phase.cells} clean gain cells · energy ×{Number(phase.mean_energy_ratio).toFixed(3)}</small></article>)}
      </section>
      <div className="pill-row"><DataPill label={`discovery ${theory.cell_count} cells`} tone="evidence" /><DataPill label={`held-out ${result.total_cells} cells`} tone="evidence" /><DataPill label="threshold frozen before validation" tone="evidence" /></div>
    </div>
  );
}
