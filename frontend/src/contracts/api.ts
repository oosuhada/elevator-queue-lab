export type ScenarioName = "morning" | "lunch" | "normal" | "evening" | "shock" | "mixed_day";

export type PolicyName = "legacy_sticky" | "nearest_car" | "collective" | "queue_aware" | "capr" | "rl";

export interface MetricsSnapshot {
  avg_wait: number;
  p95_wait: number;
  max_wait: number;
  avg_queue: number;
  little_law_lq: number;
  arrival_rate_per_min: number;
  served: number;
  arrivals: number;
  missed_capacity: number;
  abandoned: number;
  assignments: number;
  reassignments: number;
  invalidations: number;
  current_queue: number;
}

export interface ElevatorSnapshot {
  id: string;
  bank: "low" | "high";
  floor: number;
  direction: number;
  load: number;
  capacity: number;
  stops: number[];
  door_open: boolean;
  phase: string;
  target_floor: number | null;
}

export interface HallCallSnapshot {
  floor: number;
  direction: number;
  bank: "low" | "high";
  destination: number | null;
  assigned: string | null;
  wait: number;
  missed: number;
  assigned_score: number | null;
}

export interface CandidateEvaluation {
  elevator_id: string;
  pickup_eta: number;
  route_cost: number;
  projected_load: number;
  residual_capacity: number;
  insertion_index: number;
  score: number;
  feasible: boolean;
  reason: string;
  age_seconds?: number;
  capacity_shortfall?: number;
  direction_mismatch?: boolean;
  load_ratio?: number;
  score_terms?: Record<string, number>;
}

export interface DispatchDecision {
  sim_time: number;
  floor: number;
  direction: number;
  bank: string;
  destination: number | null;
  queue_size: number;
  current_assignment: string | null;
  chosen_elevator_id: string | null;
  reason: string;
  candidates: CandidateEvaluation[];
}

export interface SimulationEvent {
  sequence: number;
  sim_time: number;
  kind: string;
  passenger_id: number | null;
  elevator_id: string | null;
  floor: number | null;
  bank: string | null;
  details: Record<string, unknown>;
}

export interface HistoryPoint {
  sim_time: number;
  avg_wait: number;
  p95_wait: number;
  avg_queue: number;
}

export interface SimulationConfig {
  floors: number;
  low_zone_max: number;
  high_zone_min: number;
  elevators_per_bank: number;
  elevator_capacity: number;
  floor_height_m: number;
  max_speed_mps: number;
  acceleration_mps2: number;
  levelling_seconds: number;
  door_open_seconds: number;
  door_dwell_seconds: number;
  door_close_seconds: number;
  passenger_transfer_seconds: number;
  time_step_seconds: number;
  passenger_patience_seconds: number | null;
  control_mode: "conventional" | "destination";
  reassignment_interval_seconds: number;
  reassignment_cooldown_seconds: number;
  reassignment_min_gain: number;
  reassignment_min_eta_gain_seconds: number;
  max_noncapacity_reassignments_per_call: number;
  capacity_reserve: number;
}

export interface Snapshot {
  scenario: ScenarioName;
  policy: PolicyName;
  sim_time: number;
  clock: string;
  metrics: MetricsSnapshot;
  weights: Record<string, number>;
  elevators: ElevatorSnapshot[];
  queues: Record<string, { up: number; down: number }>;
  calls: HallCallSnapshot[];
  history: HistoryPoint[];
  audit: Record<string, unknown>;
  event_tail: SimulationEvent[];
  decision_tail: DispatchDecision[];
  trace_digest: string | null;
  simulation_config: SimulationConfig;
  running: boolean;
  speed: number;
  replay_frames: number;
  saved_replay_available: boolean;
  runtime_mode: "live_simulation" | "artifact_replay";
  playback_index?: number;
}

export interface ReplayPayload {
  schema: string;
  source: "saved_run" | "live_buffer" | "artifact_replay";
  scenario: ScenarioName;
  policy: PolicyName;
  control_mode: string;
  start_sim_time: number;
  end_sim_time: number;
  frame_count: number;
  frames: Snapshot[];
}

export interface PolicyEvidence {
  avg_wait: number;
  avg_wait_ci95_halfwidth: number;
  avg_wait_delta_ci95_halfwidth: number;
  avg_wait_delta_vs_collective: number;
  avg_wait_max: number;
  avg_wait_min: number;
  avg_wait_seed_values: number[];
  energy_proxy: number;
  guardrail_classification: string;
  p95_wait: number;
  p99_wait: number;
  worst_floor_mean_wait: number;
}

export interface ExperimentPayload {
  schema: string;
  source: string;
  baseline: {
    schema: string;
    source: Record<string, unknown>;
    scenarios: Record<string, { policies: Record<string, PolicyEvidence>; trace_digest_manifest_sha256: string }>;
  };
}

export interface TheoryPayload {
  schema: string;
  discovery: Record<string, any>;
  validation: Record<string, any>;
}

export interface RunArtifact {
  schema_version: string;
  artifact_version: string;
  simulator_version: string;
  run_id: string;
  scenario: ScenarioName;
  policy: PolicyName;
  seed: number;
  sim_time: number;
  trace_sha256: string | null;
  metrics: MetricsSnapshot;
  provenance: Record<string, any>;
  trace_manifest: Record<string, any>;
  created_at: string;
}

export interface RunsPayload {
  schema: string;
  runs: RunArtifact[];
}

export interface WorkbenchObject {
  id: string;
  object_type: string;
  [key: string]: unknown;
}

export interface ObjectsPayload {
  schema: string;
  run_id: string;
  object_types: string[];
  selected_type: string | null;
  objects: WorkbenchObject[];
  counts: Record<string, number>;
}

export interface GraphNodePayload {
  id: string;
  type: string;
  label: string;
  data: Record<string, unknown>;
}

export interface GraphEdgePayload {
  id: string;
  source: string;
  target: string;
  relation: string;
  evidence: string;
}

export interface DecisionGraphPayload {
  schema: string;
  run_id: string;
  nodes: GraphNodePayload[];
  edges: GraphEdgePayload[];
  provenance: Record<string, unknown>;
}

export interface AskRunPayload {
  schema: string;
  run_id: string;
  question: string;
  intent: string;
  answer: string;
  evidence: Array<Record<string, unknown>>;
  limitations: string[];
  expression_layer: string;
  llm_required: boolean;
}

export interface ArtifactReference {
  artifact_type: string;
  schema_version: string;
  artifact_version: string;
  artifact_id: string;
  source: string;
  sha256: string | null;
}

export interface ArtifactCatalogPayload {
  schema: string;
  run_id: string;
  artifacts: ArtifactReference[];
}

export interface ModelsPayload {
  schema: string;
  model: Record<string, any>;
  evaluation: Record<string, any>;
  source: Record<string, string>;
}
