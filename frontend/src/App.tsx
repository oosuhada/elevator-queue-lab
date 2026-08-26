import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api/client";
import { WorkbenchState } from "./components/common/WorkbenchState";
import { ProductShell, type WorkbenchKey } from "./components/shell/ProductShell";
import type {
  ArtifactCatalogPayload,
  DecisionGraphPayload,
  ExperimentPayload,
  ModelsPayload,
  ObjectsPayload,
  RunArtifact,
  Snapshot,
  TheoryPayload,
} from "./contracts/api";
import { DispatchWorkbench } from "./features/dispatch/DispatchWorkbench";
import { ExperimentsWorkbench } from "./features/experiments/ExperimentsWorkbench";
import { ExplorerWorkbench } from "./features/explorer/ExplorerWorkbench";
import { DecisionInspector } from "./features/live-operations/DecisionInspector";
import { LiveControls } from "./features/live-operations/LiveControls";
import { LiveOperations } from "./features/live-operations/LiveOperations";
import { ModelsWorkbench } from "./features/models/ModelsWorkbench";
import { RunsWorkbench } from "./features/runs/RunsWorkbench";
import { TheoryWorkbench } from "./features/theory/TheoryWorkbench";


interface AppData {
  snapshot: Snapshot;
  experiment: ExperimentPayload;
  theory: TheoryPayload;
  models: ModelsPayload;
  run: RunArtifact;
  artifacts: ArtifactCatalogPayload;
  objects: ObjectsPayload;
  graph: DecisionGraphPayload;
}

const TITLES: Record<WorkbenchKey, { title: string; subtitle: string }> = {
  live: {
    title: "Live Operations",
    subtitle: "Simulate and observe six-car group control with passenger-level evidence.",
  },
  runs: {
    title: "Runs",
    subtitle: "Inspect reproducible run provenance, trace identity, and versioned evidence artifacts.",
  },
  dispatch: {
    title: "Dispatch Analysis",
    subtitle: "Compare candidate ETA, residual capacity, feasibility, and controller score at decision time.",
  },
  experiments: {
    title: "Experiments",
    subtitle: "Compare policies across committed 30-seed statistical evidence without fabricated metrics.",
  },
  theory: {
    title: "Counterflow Criticality",
    subtitle: "Inspect the M7 discovery rule, frozen held-out validation, and its limitations.",
  },
  models: {
    title: "Models",
    subtitle: "Review M5 learned-controller metadata and the mixed/negative held-out result as recorded.",
  },
  explorer: {
    title: "Object Explorer",
    subtitle: "Trace passengers, hall calls, decisions, elevators, evidence, and theory through a run projection.",
  },
};

function workbenchFromHash(): WorkbenchKey {
  const candidate = window.location.hash.replace(/^#\/?/, "") as WorkbenchKey;
  return candidate && candidate in TITLES ? candidate : "live";
}

async function loadRunContext(run: RunArtifact): Promise<Pick<AppData, "artifacts" | "objects" | "graph">> {
  const [artifacts, objects, graph] = await Promise.all([
    api.artifacts(),
    api.objects(run.run_id),
    api.graph(run.run_id),
  ]);
  return { artifacts, objects, graph };
}

export default function App() {
  const [active, setActive] = useState<WorkbenchKey>(workbenchFromHash);
  const [data, setData] = useState<AppData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [inspectionSnapshot, setInspectionSnapshot] = useState<Snapshot | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [snapshot, experiment, theory, models, runs] = await Promise.all([
          api.snapshot(),
          api.experiment(),
          api.theory(),
          api.models(),
          api.runs(),
        ]);
        const run = runs.runs[0];
        if (!run) throw new Error("No live SimulationRunArtifact was returned.");
        const context = await loadRunContext(run);
        if (!cancelled) setData({ snapshot, experiment, theory, models, run, ...context });
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!data) return;
    const timer = window.setInterval(() => {
      void api.snapshot().then((snapshot) => setData((current) => current ? { ...current, snapshot } : current)).catch(() => undefined);
    }, 600);
    return () => window.clearInterval(timer);
  }, [Boolean(data)]);

  useEffect(() => {
    if (!data || active !== "explorer") return;
    const refresh = () => {
      void Promise.all([api.objects(data.run.run_id), api.graph(data.run.run_id)]).then(([objects, graph]) => {
        setData((current) => current ? { ...current, objects, graph } : current);
      }).catch(() => undefined);
    };
    refresh();
    const timer = window.setInterval(refresh, 2500);
    return () => window.clearInterval(timer);
  }, [active, data?.run.run_id]);

  const refreshRunIdentity = useCallback(async () => {
    const runs = await api.runs();
    const run = runs.runs[0];
    if (!run) throw new Error("Run identity disappeared after control update.");
    const context = await loadRunContext(run);
    setData((current) => current ? { ...current, run, ...context } : current);
  }, []);

  const handleControl = useCallback(async (payload: Record<string, unknown>) => {
    if (!data) return;
    setError(null);
    try {
      const snapshot = await api.control(payload);
      setData((current) => current ? { ...current, snapshot } : current);
      await refreshRunIdentity();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, [data, refreshRunIdentity]);

  function navigate(next: WorkbenchKey) {
    setActive(next);
    window.location.hash = next;
  }

  if (error && !data) {
    return <div className="boot-state"><WorkbenchState kind="error" title="Workbench failed to initialize">{error}</WorkbenchState></div>;
  }
  if (!data) {
    return <div className="boot-state"><WorkbenchState kind="loading" title="Loading simulator and committed evidence" /></div>;
  }

  const copy = TITLES[active];
  const latestDecision = (inspectionSnapshot ?? data.snapshot).decision_tail.at(-1);
  const decisionSnapshot = inspectionSnapshot ?? data.snapshot;
  const toolbar = active === "live" ? <LiveControls snapshot={data.snapshot} onControl={handleControl} /> : undefined;
  const inspector = active === "live" ? <DecisionInspector decision={latestDecision} snapshot={decisionSnapshot} /> : undefined;
  let content: React.ReactNode;
  if (active === "live") {
    content = <LiveOperations liveSnapshot={data.snapshot} onControl={handleControl} onSaveReplay={api.saveReplay} onInspectionSnapshotChange={setInspectionSnapshot} />;
  } else if (active === "runs") {
    content = <RunsWorkbench run={data.run} artifacts={data.artifacts} />;
  } else if (active === "dispatch") {
    content = <DispatchWorkbench snapshot={data.snapshot} />;
  } else if (active === "experiments") {
    content = <ExperimentsWorkbench payload={data.experiment} />;
  } else if (active === "theory") {
    content = <TheoryWorkbench payload={data.theory} />;
  } else if (active === "models") {
    content = <ModelsWorkbench payload={data.models} />;
  } else {
    content = <ExplorerWorkbench runId={data.run.run_id} initialObjects={data.objects} graph={data.graph} />;
  }

  return (
    <ProductShell
      active={active}
      onNavigate={navigate}
      title={copy.title}
      subtitle={copy.subtitle}
      toolbar={toolbar}
      inspector={inspector}
      inspectorOpen={inspectorOpen}
      onToggleInspector={() => setInspectorOpen((value) => !value)}
      status={{
        mode: data.snapshot.running ? "LIVE" : "PAUSED",
        scenario: data.snapshot.scenario,
        policy: data.snapshot.policy,
        runId: data.run.run_id,
        provenance: data.run.trace_sha256 ? "materialized passenger trace" : "seeded demand generator",
      }}
    >
      {error ? <WorkbenchState kind="error" title="Latest action failed">{error}</WorkbenchState> : null}
      {content}
    </ProductShell>
  );
}
