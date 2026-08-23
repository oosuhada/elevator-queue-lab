import { DataPill } from "../../components/common/DataPill";
import type { ModelsPayload } from "../../contracts/api";


export function ModelsWorkbench({ payload }: { payload: ModelsPayload }) {
  const model = payload.model;
  const evaluation = payload.evaluation;
  const metadata = model.metadata ?? {};
  const verdict = evaluation.verdict ?? {};
  const headline = Array.isArray(evaluation.headline) ? evaluation.headline : [];
  return (
    <div className="analysis-workbench models-workbench" data-testid="models-workbench">
      <section className="negative-result-card">
        <span>M5 held-out verdict</span>
        <strong>Learned-controller superiority was not established.</strong>
        <p>{String(verdict.interpretation ?? "Held-out evidence does not support a general superiority claim.")}</p>
        <div className="pill-row"><DataPill label="negative / mixed result" tone="warning" /><DataPill label="not hidden" tone="evidence" /></div>
      </section>
      <section className="evidence-detail-grid">
        <article><span>Architecture</span><strong>{String(model.architecture ?? "—")}</strong></article>
        <article><span>Observation space</span><strong>{String(model.observation_size ?? "—")} values</strong></article>
        <article><span>Actions</span><strong>{Array.isArray(model.actions) ? model.actions.length : 0}</strong></article>
        <article><span>Training seed</span><strong>{String(metadata.training_seed ?? "—")}</strong></article>
      </section>
      <div className="chart-grid-two">
        <section className="panel-card">
          <header className="section-heading"><div><span>Training contract</span><strong>Reproducible checkpoint provenance</strong></div></header>
          <dl className="diagnostic-list">
            <div><dt>Algorithm</dt><dd>{String(metadata.algorithm ?? model.architecture)}</dd></div>
            <div><dt>Epochs</dt><dd>{String(metadata.epochs ?? "—")}</dd></div>
            <div><dt>Episodes</dt><dd>{String(metadata.episodes ?? "—")}</dd></div>
            <div><dt>Gradient steps</dt><dd>{String(metadata.gradient_steps ?? "—")}</dd></div>
            <div><dt>Training scenarios</dt><dd>{Array.isArray(metadata.training_scenarios) ? metadata.training_scenarios.join(", ") : "—"}</dd></div>
            <div><dt>Held-out scenarios</dt><dd>{Array.isArray(metadata.held_out_scenarios) ? metadata.held_out_scenarios.join(", ") : "—"}</dd></div>
          </dl>
        </section>
        <section className="panel-card">
          <header className="section-heading"><div><span>Action contract</span><strong>Discrete dispatch decisions</strong></div></header>
          <div className="action-chip-list">{Array.isArray(model.actions) ? model.actions.map((action: unknown) => <span key={String(action)}>{String(action)}</span>) : null}</div>
          <p className="evidence-note">The learned policy runs through the same simulator assignment/reassignment invariants. Newer model architecture is not presented as automatically better.</p>
        </section>
      </div>
      <section className="panel-card">
        <header className="section-heading"><div><span>Held-out performance</span><strong>Collective · CAPR · RL</strong></div></header>
        <div className="compact-table-wrap"><table className="compact-table"><caption>M5 scenario evidence</caption><thead><tr><th>Scenario</th><th>Policy</th><th>AWT</th><th>P95</th><th>Worst floor</th><th>Energy</th><th>Guardrail</th></tr></thead><tbody>{headline.map((row: any, index: number) => <tr key={`${row.scenario}-${row.policy}-${index}`}><td>{row.scenario}</td><td>{row.policy}</td><td>{Number(row.avg_wait).toFixed(2)}</td><td>{Number(row.p95_wait).toFixed(2)}</td><td>{Number(row.worst_floor_mean_wait).toFixed(2)}</td><td>{Number(row.energy_proxy).toFixed(1)}</td><td>{row.guardrail}</td></tr>)}</tbody></table></div>
      </section>
      <section className="panel-card"><header className="section-heading"><div><span>Model artifact provenance</span><strong>{payload.source.model}</strong></div></header><pre className="json-preview">{JSON.stringify({ schema: model.schema, training_contract: evaluation.training_contract, held_out_contract: evaluation.held_out_contract, verdict }, null, 2)}</pre></section>
    </div>
  );
}
