import type {
  ArtifactCatalogPayload,
  AskRunPayload,
  DecisionGraphPayload,
  ExperimentPayload,
  ModelsPayload,
  ObjectsPayload,
  ReplayPayload,
  RunsPayload,
  Snapshot,
  TheoryPayload,
} from "../contracts/api";


async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-store", ...init });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${message}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  snapshot: (): Promise<Snapshot> => requestJson("/api/snapshot"),
  experiment: (): Promise<ExperimentPayload> => requestJson("/api/experiment"),
  theory: (): Promise<TheoryPayload> => requestJson("/api/theory"),
  models: (): Promise<ModelsPayload> => requestJson("/api/models"),
  artifacts: (): Promise<ArtifactCatalogPayload> => requestJson("/api/artifacts"),
  runs: (): Promise<RunsPayload> => requestJson("/api/runs"),
  objects: (runId: string, objectType?: string): Promise<ObjectsPayload> => {
    const query = objectType ? `?type=${encodeURIComponent(objectType)}` : "";
    return requestJson(`/api/runs/${encodeURIComponent(runId)}/objects${query}`);
  },
  graph: (runId: string): Promise<DecisionGraphPayload> =>
    requestJson(`/api/runs/${encodeURIComponent(runId)}/graph`),
  ask: (runId: string, question: string): Promise<AskRunPayload> =>
    requestJson(`/api/runs/${encodeURIComponent(runId)}/ask?q=${encodeURIComponent(question)}`),
  control: (payload: Record<string, unknown>): Promise<Snapshot> =>
    requestJson("/api/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  replay: (): Promise<ReplayPayload> => requestJson("/api/replay"),
  saveReplay: (): Promise<ReplayPayload> =>
    requestJson("/api/replay", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "save" }),
    }),
};
