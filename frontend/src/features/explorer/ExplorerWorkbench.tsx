import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { DataPill } from "../../components/common/DataPill";
import { WorkbenchState } from "../../components/common/WorkbenchState";
import type { AskRunPayload, DecisionGraphPayload, ObjectsPayload, WorkbenchObject } from "../../contracts/api";
import { DecisionTraceGraph } from "./DecisionTraceGraph";


interface ExplorerWorkbenchProps {
  runId: string;
  initialObjects: ObjectsPayload;
  graph: DecisionGraphPayload;
}

function displayName(item: WorkbenchObject): string {
  if (typeof item.name === "string") return item.name;
  if (typeof item.passenger_id === "number") return `Passenger P-${item.passenger_id}`;
  if (item.object_type === "HallCall") return `${String(item.floor)}F ${Number(item.direction) > 0 ? "↑" : "↓"}`;
  if (item.object_type === "DispatchDecision") return `${item.id} · ${String(item.chosen_elevator_id ?? "unassigned")}`;
  return item.id;
}

function ObjectDetail({ selection }: { selection: WorkbenchObject | Record<string, unknown> | null }) {
  if (!selection) return <WorkbenchState kind="empty" title="Select an object or graph relationship" />;
  return (
    <div className="object-detail">
      <header><span>Evidence inspector</span><strong>{String(selection.id ?? selection.kind ?? "selection")}</strong></header>
      <dl>
        {Object.entries(selection).filter(([key]) => !["candidates", "provenance", "trace_manifest", "metadata"].includes(key)).slice(0, 18).map(([key, value]) => (
          <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{typeof value === "object" ? JSON.stringify(value) : String(value ?? "—")}</dd></div>
        ))}
      </dl>
      {["candidates", "provenance", "trace_manifest", "metadata"].map((key) => selection[key] ? (
        <details key={key}><summary>{key.replaceAll("_", " ")}</summary><pre className="json-preview">{JSON.stringify(selection[key], null, 2)}</pre></details>
      ) : null)}
    </div>
  );
}

export function ExplorerWorkbench({ runId, initialObjects, graph }: ExplorerWorkbenchProps) {
  const [objectType, setObjectType] = useState("Passenger");
  const [payload, setPayload] = useState(initialObjects);
  const [selected, setSelected] = useState<WorkbenchObject | Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [question, setQuestion] = useState("Why did CAPR choose this elevator?");
  const [answer, setAnswer] = useState<AskRunPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.objects(runId, objectType).then((next) => {
      if (!active) return;
      setPayload(next);
      setSelected(next.objects[0] ?? null);
      setLoading(false);
    }).catch((cause: unknown) => {
      if (!active) return;
      setError(cause instanceof Error ? cause.message : String(cause));
      setLoading(false);
    });
    return () => { active = false; };
  }, [runId, objectType]);

  async function askRun() {
    setError(null);
    try {
      setAnswer(await api.ask(runId, question));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }

  return (
    <div className="explorer-workbench" data-testid="explorer-workbench">
      <div className="object-explorer-grid">
        <aside className="object-type-list" aria-label="Object types">
          <header><span>Object types</span><strong>{initialObjects.object_types.length}</strong></header>
          {initialObjects.object_types.map((type) => (
            <button key={type} type="button" className={objectType === type ? "is-active" : ""} onClick={() => setObjectType(type)}>
              <span>{type}</span><small>{initialObjects.counts[type] ?? 0}</small>
            </button>
          ))}
        </aside>
        <section className="object-list-pane">
          <header className="section-heading"><div><span>{objectType}</span><strong>Run objects</strong></div><DataPill label={`${payload.objects.length} visible`} /></header>
          {loading ? <WorkbenchState kind="loading" title="Loading object projection" /> : (
            <div className="object-list">
              {payload.objects.length ? payload.objects.map((item) => (
                <button key={item.id} type="button" className={selected?.id === item.id ? "is-active" : ""} onClick={() => setSelected(item)}>
                  <strong>{displayName(item)}</strong><span>{item.object_type}</span>
                </button>
              )) : <WorkbenchState kind="empty" title="No objects in the current retained run state" />}
            </div>
          )}
        </section>
        <aside className="object-detail-inspector"><ObjectDetail selection={selected} /></aside>
      </div>

      <DecisionTraceGraph graph={graph} onSelect={setSelected} />

      <section className="ask-run-card">
        <header className="section-heading"><div><span>Ask This Run</span><strong>Deterministic evidence query</strong></div><DataPill label="LLM not required" tone="evidence" /></header>
        <div className="ask-run-form">
          <input aria-label="Ask this run question" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void askRun(); }} />
          <button className="primary-button" type="button" onClick={askRun}>Query evidence</button>
        </div>
        <div className="suggested-questions">
          {["Compare this run with collective", "Why was this call reassigned?", "What caused the P95 spike?"].map((item) => <button key={item} type="button" onClick={() => setQuestion(item)}>{item}</button>)}
        </div>
        {error ? <WorkbenchState kind="error" title="Evidence query failed">{error}</WorkbenchState> : null}
        {answer ? (
          <article className="ask-run-answer">
            <span>{answer.intent.replaceAll("_", " ")}</span>
            <strong>{answer.answer}</strong>
            <details><summary>{answer.evidence.length} evidence package item(s)</summary><pre className="json-preview">{JSON.stringify(answer.evidence, null, 2)}</pre></details>
            <small>{answer.limitations.join(" ")}</small>
          </article>
        ) : null}
      </section>
    </div>
  );
}
