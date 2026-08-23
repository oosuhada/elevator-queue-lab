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

type EvidenceVerdict = "clean-win" | "trade-off" | "regression" | "insufficient" | "falsification" | "reference";

const VERDICT_COPY: Record<EvidenceVerdict, { symbol: string; label: string; detail: string }> = {
  "clean-win": { symbol: "◆", label: "clean win", detail: "Mean wait improves and configured guardrails stay within tolerance." },
  "trade-off": { symbol: "△", label: "trade-off", detail: "Mean wait improves, but at least one service/fairness/energy guardrail trades off." },
  regression: { symbol: "×", label: "regression", detail: "Mean wait does not improve versus the collective reference." },
  insufficient: { symbol: "○", label: "insufficient evidence", detail: "The paired mean delta is not larger than its committed 95% CI half-width." },
  falsification: { symbol: "⊘", label: "falsification", detail: "The candidate hypothesis fails to improve mean wait in this traffic regime." },
  reference: { symbol: "│", label: "reference", detail: "Collective is the comparison reference, not a declared winner." },
};

function evidenceVerdict(policy: string, evidence: PolicyEvidence): EvidenceVerdict {
  if (evidence.guardrail_classification === "reference") return "reference";
  if (Math.abs(evidence.avg_wait_delta_vs_collective) <= evidence.avg_wait_delta_ci95_halfwidth) return "insufficient";
  if (evidence.guardrail_classification === "candidate_improvement") return "clean-win";
  if (evidence.guardrail_classification === "mean_improves_with_guardrail_tradeoff") return "trade-off";
  if (policy === "capr" && evidence.guardrail_classification === "no_mean_improvement") return "falsification";
  return "regression";
}

function verdictRank(policy: string, evidence: PolicyEvidence): number {
  return {
    "clean-win": 0,
    reference: 1,
    "trade-off": 2,
    insufficient: 3,
    regression: 4,
    falsification: 5,
  }[evidenceVerdict(policy, evidence)];
}

function fmt(value: number, digits = 2): string {
  return Number(value).toFixed(digits);
}

export function ExperimentsWorkbench({ payload }: { payload: ExperimentPayload }) {
  const [scenario, setScenario] = useState("lunch");
  const [metric, setMetric] = useState("avg_wait");
  const policies = payload.baseline.scenarios[scenario]?.policies ?? {};
  const ranked = useMemo(() => POLICY_ORDER.filter((policy) => policies[policy]).map((policy) => ({ policy, evidence: policies[policy] })).sort((a, b) => {
    const guardrail = verdictRank(a.policy, a.evidence) - verdictRank(b.policy, b.evidence);
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
            <span>{index === 0 ? "Scenario evidence order" : `Rank ${index + 1}`}</span>
            <strong>{POLICY_LABELS[policy]}</strong>
            <small>{evidence.avg_wait.toFixed(2)}s AWT · {VERDICT_COPY[evidenceVerdict(policy, evidence)].label}</small>
          </article>
        ))}
      </section>

      <section className="verdict-legend" aria-label="Experiment verdict legend">
        {(Object.entries(VERDICT_COPY) as Array<[EvidenceVerdict, (typeof VERDICT_COPY)[EvidenceVerdict]]>).filter(([key]) => key !== "reference").map(([key, copy]) => (
          <div key={key} className={`verdict-key verdict-${key}`}><b aria-hidden="true">{copy.symbol}</b><span><strong>{copy.label}</strong><small>{copy.detail}</small></span></div>
        ))}
      </section>

      <section id="comparison-cards" className="comparison-cards">
        {POLICY_ORDER.filter((policy) => policies[policy]).map((policy) => {
          const evidence = policies[policy];
          const delta = collective ? evidence.avg_wait - collective.avg_wait : 0;
          const verdict = evidenceVerdict(policy, evidence);
          const verdictCopy = VERDICT_COPY[verdict];
          return (
            <article key={policy} className={`comparison-card verdict-${verdict}`} data-policy={policy} data-verdict={verdict}>
              <span className="comparison-card-title"><b aria-hidden="true">{verdictCopy.symbol}</b>{POLICY_LABELS[policy]}</span>
              <strong>{fmt(evidence.avg_wait)}s</strong>
              <small>P95 {fmt(evidence.p95_wait)}s · P99 {fmt(evidence.p99_wait)}s</small>
              <small>95% CI ±{fmt(evidence.avg_wait_ci95_halfwidth)}s</small>
              <small>vs collective {delta >= 0 ? "+" : ""}{fmt(delta)}s</small>
              <span className="verdict-label"><b>{verdictCopy.label}</b><small>{verdictCopy.detail}</small></span>
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
              {ranked.map(({ policy, evidence }) => {
                const verdict = evidenceVerdict(policy, evidence);
                return <tr key={policy} data-policy={policy}><td>{POLICY_LABELS[policy]}</td><td>{fmt(evidence.avg_wait)}</td><td>{fmt(evidence.p95_wait)}</td><td>{fmt(evidence.p99_wait)}</td><td>{fmt(evidence.worst_floor_mean_wait)}</td><td>{fmt(evidence.energy_proxy, 1)}</td><td>{fmt(evidence.avg_wait_delta_vs_collective)}</td><td><span className={`table-verdict verdict-${verdict}`}><b aria-hidden="true">{VERDICT_COPY[verdict].symbol}</b>{VERDICT_COPY[verdict].label}</span></td></tr>;
              })}
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
