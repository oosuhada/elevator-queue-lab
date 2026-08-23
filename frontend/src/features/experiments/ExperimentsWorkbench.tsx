import { useMemo, useState } from "react";
import { ChartRenderer } from "../../components/charts/ChartRenderer";
import { DataPill } from "../../components/common/DataPill";
import type { ExperimentPayload, PolicyEvidence } from "../../contracts/api";
import type { ChartSpec } from "../../contracts/chartSpec";


const POLICY_ORDER = ["legacy_sticky", "nearest_car", "collective", "queue_aware", "capr"];
const POLICY_LABELS: Record<string, string> = {
  legacy_sticky: "Legacy sticky",
  nearest_car: "Nearest car",
  collective: "Collective",
  queue_aware: "Queue-aware",
  capr: "CAPR",
};

function classificationRank(classification: string): number {
  return {
    candidate_improvement: 0,
    reference: 1,
    mean_improves_with_guardrail_tradeoff: 2,
    no_mean_improvement: 3,
  }[classification] ?? 4;
}

function fmt(value: number, digits = 2): string {
  return Number(value).toFixed(digits);
}

export function ExperimentsWorkbench({ payload }: { payload: ExperimentPayload }) {
  const [scenario, setScenario] = useState("lunch");
  const [metric, setMetric] = useState("avg_wait");
  const policies = payload.baseline.scenarios[scenario]?.policies ?? {};
  const ranked = useMemo(() => POLICY_ORDER.filter((policy) => policies[policy]).map((policy) => ({ policy, evidence: policies[policy] })).sort((a, b) => {
    const guardrail = classificationRank(a.evidence.guardrail_classification) - classificationRank(b.evidence.guardrail_classification);
    return guardrail || a.evidence.avg_wait - b.evidence.avg_wait;
  }), [policies]);
  const selectedPolicy = ranked[0]?.policy ?? "collective";
  const selected = policies[selectedPolicy];
  const collective = policies.collective;
  const distributionSpec: ChartSpec = {
    type: "distribution",
    title: "30-seed AWT distribution",
    source: payload.source,
    metric: "avg_wait",
    groupBy: "policy",
    scenario,
    confidenceInterval: true,
  };
  const ciSpec: ChartSpec = {
    type: "confidenceInterval",
    title: "Mean AWT · 95% confidence interval",
    source: payload.source,
    metric: "avg_wait",
    scenario,
    groupBy: "policy",
  };
  const tradeoffSpec: ChartSpec = {
    type: "tradeoff",
    title: "Energy / wait tradeoff",
    source: payload.source,
    x: "energy_proxy",
    y: "avg_wait",
    groupBy: "policy",
    scenario,
    reference: "collective",
  };
  const matrixSpec: ChartSpec = {
    type: "experimentMatrix",
    title: "Scenario × policy matrix",
    source: payload.source,
    metric,
    row: "scenario",
    column: "policy",
  };

  return (
    <div className="analysis-workbench" data-testid="experiments-workbench">
      <section className="analysis-control-strip">
        <label>Scenario<select id="evidence-scenario" value={scenario} onChange={(event) => setScenario(event.target.value)}>{Object.keys(payload.baseline.scenarios).map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
        <label>Metric<select value={metric} onChange={(event) => setMetric(event.target.value)}><option value="avg_wait">Mean AWT</option><option value="p95_wait">P95 wait</option><option value="p99_wait">P99 wait</option><option value="worst_floor_mean_wait">Worst-floor mean</option><option value="energy_proxy">Energy proxy</option></select></label>
        <DataPill label="common random numbers" tone="evidence" />
        <DataPill label="30 seeds" tone="evidence" />
      </section>

      <section id="policy-leaders" className="policy-leaders" aria-label="Evidence leaders">
        {ranked.slice(0, 3).map(({ policy, evidence }, index) => (
          <article key={policy} className={`policy-leader ${index === 0 ? "primary" : ""}`} data-policy={policy}>
            <span>{index === 0 ? "Evidence leader" : `Rank ${index + 1}`}</span>
            <strong>{POLICY_LABELS[policy]}</strong>
            <small>{evidence.avg_wait.toFixed(2)}s AWT · {evidence.guardrail_classification.replaceAll("_", " ")}</small>
          </article>
        ))}
      </section>

      <section id="comparison-cards" className="comparison-cards">
        {POLICY_ORDER.filter((policy) => policies[policy]).map((policy) => {
          const evidence = policies[policy];
          const delta = collective ? evidence.avg_wait - collective.avg_wait : 0;
          return (
            <article key={policy} className="comparison-card" data-policy={policy}>
              <span>{POLICY_LABELS[policy]}</span>
              <strong>{fmt(evidence.avg_wait)}s</strong>
              <small>P95 {fmt(evidence.p95_wait)}s · P99 {fmt(evidence.p99_wait)}s</small>
              <small>95% CI ±{fmt(evidence.avg_wait_ci95_halfwidth)}s</small>
              <small>vs collective {delta >= 0 ? "+" : ""}{fmt(delta)}s</small>
              <DataPill label={evidence.guardrail_classification.replaceAll("_", " ")} tone={evidence.guardrail_classification === "candidate_improvement" ? "live" : "neutral"} />
            </article>
          );
        })}
      </section>

      {selected ? <EvidenceDetail policy={selectedPolicy} evidence={selected} /> : null}
      <div className="chart-grid-two"><ChartRenderer spec={distributionSpec} data={payload} /><ChartRenderer spec={ciSpec} data={payload} /></div>
      <div className="chart-grid-two"><ChartRenderer spec={tradeoffSpec} data={payload} /><ChartRenderer spec={matrixSpec} data={payload} /></div>

      <section className="panel-card">
        <header className="section-heading"><div><span>Policy ranking</span><strong>Committed M3 evidence only</strong></div></header>
        <div className="compact-table-wrap">
          <table className="compact-table">
            <caption>{scenario} policy evidence</caption>
            <thead><tr><th>Policy</th><th>Mean</th><th>P95</th><th>P99</th><th>Worst floor</th><th>Energy</th><th>Paired Δ</th><th>Guardrail</th></tr></thead>
            <tbody id="policy-ranking-body">
              {ranked.map(({ policy, evidence }) => <tr key={policy} data-policy={policy}><td>{POLICY_LABELS[policy]}</td><td>{fmt(evidence.avg_wait)}</td><td>{fmt(evidence.p95_wait)}</td><td>{fmt(evidence.p99_wait)}</td><td>{fmt(evidence.worst_floor_mean_wait)}</td><td>{fmt(evidence.energy_proxy, 1)}</td><td>{fmt(evidence.avg_wait_delta_vs_collective)}</td><td>{evidence.guardrail_classification.replaceAll("_", " ")}</td></tr>)}
            </tbody>
          </table>
        </div>
        <p className="evidence-note">P50, fairness, capacity misses, and reassignment latency are shown only when a committed artifact exposes those aggregations. The M3 regression baseline does not contain every one of those fields, so this UI does not synthesize them.</p>
      </section>
    </div>
  );
}

function EvidenceDetail({ policy, evidence }: { policy: string; evidence: PolicyEvidence }) {
  return (
    <section className="evidence-detail-grid">
      <article><span>Selected policy</span><strong>{POLICY_LABELS[policy]}</strong></article>
      <article><span>Worst-floor mean</span><strong>{evidence.worst_floor_mean_wait.toFixed(2)}s</strong></article>
      <article><span>Energy proxy</span><strong>{evidence.energy_proxy.toFixed(1)}</strong></article>
      <article><span>Paired Δ CI</span><strong>±{evidence.avg_wait_delta_ci95_halfwidth.toFixed(2)}s</strong></article>
    </section>
  );
}
