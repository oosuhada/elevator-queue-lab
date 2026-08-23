import { DataPill } from "../../components/common/DataPill";
import type { ArtifactCatalogPayload, RunArtifact } from "../../contracts/api";


export function RunsWorkbench({ run, artifacts }: { run: RunArtifact; artifacts: ArtifactCatalogPayload }) {
  return (
    <div className="analysis-workbench runs-workbench" data-testid="runs-workbench">
      <section className="run-hero-card">
        <div><span>SimulationRunArtifact</span><strong>{run.run_id}</strong><small>{run.schema_version} · artifact {run.artifact_version}</small></div>
        <div className="pill-row"><DataPill label="scenario" value={run.scenario} /><DataPill label="policy" value={run.policy.toUpperCase()} tone="evidence" /><DataPill label="seed" value={run.seed} /></div>
      </section>
      <section className="evidence-detail-grid">
        <article><span>Simulation time</span><strong>{run.sim_time}s</strong></article>
        <article><span>Average wait</span><strong>{run.metrics.avg_wait.toFixed(2)}s</strong></article>
        <article><span>P95 wait</span><strong>{run.metrics.p95_wait.toFixed(2)}s</strong></article>
        <article><span>Trace identity</span><strong className="hash-text">{String(run.provenance.trace_identity_sha256 ?? "—").slice(0, 16)}…</strong></article>
      </section>
      <div className="chart-grid-two">
        <section className="panel-card"><header className="section-heading"><div><span>Trace manifest</span><strong>Canonical reproducibility package</strong></div></header><pre className="json-preview">{JSON.stringify(run.trace_manifest, null, 2)}</pre></section>
        <section className="panel-card"><header className="section-heading"><div><span>Run provenance</span><strong>Evidence lineage</strong></div></header><pre className="json-preview">{JSON.stringify(run.provenance, null, 2)}</pre></section>
      </div>
      <section className="panel-card"><header className="section-heading"><div><span>Artifact catalog</span><strong>Versioned evidence references</strong></div></header><div className="compact-table-wrap"><table className="compact-table"><caption>Run and committed evidence artifacts</caption><thead><tr><th>Type</th><th>Schema</th><th>Source</th><th>SHA-256</th></tr></thead><tbody>{artifacts.artifacts.map((artifact) => <tr key={artifact.artifact_id}><td>{artifact.artifact_type}</td><td>{artifact.schema_version}</td><td>{artifact.source}</td><td className="hash-text">{artifact.sha256?.slice(0, 16) ?? "live"}</td></tr>)}</tbody></table></div></section>
    </div>
  );
}
