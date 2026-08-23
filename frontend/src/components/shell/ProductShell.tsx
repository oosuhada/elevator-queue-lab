import type { ReactNode } from "react";
import { DataPill } from "../common/DataPill";


export type WorkbenchKey = "live" | "runs" | "dispatch" | "experiments" | "theory" | "models" | "explorer";

interface ProductShellProps {
  active: WorkbenchKey;
  onNavigate: (next: WorkbenchKey) => void;
  title: string;
  subtitle: string;
  toolbar?: ReactNode;
  inspector?: ReactNode;
  inspectorOpen?: boolean;
  onToggleInspector?: () => void;
  status: {
    mode: string;
    scenario?: string;
    policy?: string;
    runId?: string;
    provenance?: string;
  };
  children: ReactNode;
}

const NAV_ITEMS: Array<{ key: WorkbenchKey; label: string; short: string }> = [
  { key: "live", label: "Live Operations", short: "LO" },
  { key: "runs", label: "Runs", short: "RU" },
  { key: "dispatch", label: "Dispatch Analysis", short: "DA" },
  { key: "experiments", label: "Experiments", short: "EX" },
  { key: "theory", label: "Theory", short: "TH" },
  { key: "models", label: "Models", short: "MO" },
  { key: "explorer", label: "Explorer", short: "OB" },
];

export function ProductShell({
  active,
  onNavigate,
  title,
  subtitle,
  toolbar,
  inspector,
  inspectorOpen = true,
  onToggleInspector,
  status,
  children,
}: ProductShellProps) {
  return (
    <div className="product-shell">
      <header className="global-header">
        <button className="brand-mark" type="button" onClick={() => onNavigate("live")} aria-label="Open Live Operations">
          EQL
        </button>
        <div className="brand-copy">
          <strong>Elevator Queue Lab</strong>
          <span>Decision Intelligence Workbench</span>
        </div>
        <div className="global-header-status">
          <DataPill label={status.mode} tone={status.mode === "LIVE" ? "live" : "neutral"} />
          {status.scenario ? <DataPill label="scenario" value={status.scenario} /> : null}
          {status.policy ? <DataPill label="policy" value={status.policy.toUpperCase()} tone="evidence" /> : null}
        </div>
      </header>

      <aside className="product-rail" aria-label="Workbench navigation">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.key}
            className={active === item.key ? "rail-button is-active" : "rail-button"}
            type="button"
            title={item.label}
            aria-label={item.label}
            aria-current={active === item.key ? "page" : undefined}
            onClick={() => onNavigate(item.key)}
          >
            <span aria-hidden="true">{item.short}</span>
            <small>{item.label}</small>
          </button>
        ))}
      </aside>

      <section className="resource-surface">
        <div className="resource-header">
          <div>
            <span className="resource-eyebrow">{active.replace("-", " ")}</span>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          {inspector ? (
            <button className="secondary-button inspector-toggle" type="button" onClick={onToggleInspector}>
              {inspectorOpen ? "Hide inspector" : "Show inspector"}
            </button>
          ) : null}
        </div>
        {toolbar ? <div className="workbench-toolbar">{toolbar}</div> : null}
        <div className={inspector && inspectorOpen ? "workbench-layout has-inspector" : "workbench-layout"}>
          <main className="workbench-main">{children}</main>
          {inspector && inspectorOpen ? <aside className="inspector-pane">{inspector}</aside> : null}
        </div>
      </section>

      <footer className="status-bar">
        <span>provenance: {status.provenance ?? "live simulator"}</span>
        <span>{status.runId ?? "run pending"}</span>
        <span>seeded reproducibility · no fabricated metrics</span>
      </footer>
    </div>
  );
}
