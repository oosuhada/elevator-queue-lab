# M8 — Decision Intelligence Product Workbench

M8 evolves Elevator Queue Lab from a research simulator with a dashboard into a reproducible
decision-intelligence workbench. The simulator remains authoritative. The product layer adds typed
projections over existing simulator state, ledgers and committed evidence so a reviewer can move
through the full research loop:

`SIMULATE → OBSERVE → INSPECT → EXPLAIN → REPLAY → COMPARE → FALSIFY`

> Elevator Queue Lab is a reproducible decision-intelligence workbench for elevator group-control
> research: simulate, compare, inspect, replay, explain, and falsify dispatch decisions from
> passenger-level evidence.

## 1. Previous architecture

Before M8 the runtime was already research-grade but the browser surface was concentrated in a
large vanilla-JavaScript implementation:

```text
app/ simulator + server
        ↓ JSON API
web/index.html
web/app.js
web/queue-trend.js
web/styles.css
```

That architecture delivered deterministic replay, API-consistent live state, committed experiment
evidence and the M7 theory panel. Its main limitation was product composition: navigation, object
exploration, analytics renderers and inspector behavior were difficult to evolve independently.

## 2. M8 architecture

M8 keeps the Python simulator and HTTP server intact and inserts read-only evidence projections
between the core and the product workbenches.

```text
Passenger demand / canonical trace
                ↓
       ElevatorSimulation
       ├─ snapshot state
       ├─ decision history
       └─ event ledger
                ↓
      read-only projections
       ├─ run artifacts
       ├─ object catalog
       ├─ decision graph
       └─ deterministic explanations
                ↓
          Python HTTP API
                ↓
frontend/ React + TypeScript source
       ├─ Product Shell
       ├─ Live Operations
       ├─ Runs / Dispatch
       ├─ Experiments / Theory / Models
       └─ Object Explorer / Decision Trace
                ↓ Vite build
web/ committed production artifact
                ↓
python -m app.server --port 4173
```

The important boundary is one-way: the workbench can inspect and request simulator controls, but
it does not replace simulator truth with browser-side state or generated analytics.

## 3. Frontend boundary

`frontend/` is the authored UI source. It contains React components, TypeScript API contracts,
semantic chart specifications, tests and design tokens. `frontend/vite.config.ts` builds directly
to `../web` with `emptyOutDir: true`.

`web/` is therefore a deployment artifact, not a second authored frontend. A clean checkout can
still run the product with only Python because the production build is committed:

```bash
python3 -m app.server --port 4173
```

Frontend contributors use:

```bash
npm ci --prefix frontend
npm run typecheck --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

The migration intentionally preserves the existing Python static-serving path and Mac mini
service/proxy deployment contract.

## 4. Simulation-core boundary

M8 does not rewrite the elevator engine, CAPR controller, traffic generator, experiment runner or
learning environment. `app/artifacts.py` and `app/workbench.py` project existing data into
product-oriented contracts.

The projections are read-only with respect to the research core:

- live state comes from `ElevatorSimulation.snapshot()`;
- passenger lifecycle evidence comes from the event ledger;
- candidate and assignment evidence comes from `decision_history`;
- statistical comparisons come from committed evidence JSON;
- learned-controller claims come from the committed M5 model/evaluation artifacts;
- counterflow claims come from committed M7 discovery and held-out validation artifacts.

No Neo4j, PostgreSQL or secondary analytical source of truth is introduced.

## 5. Versioned evidence artifacts

M8 exposes a catalog containing these artifact types:

| Artifact type | Primary source | Purpose |
| --- | --- | --- |
| `PassengerTraceArtifact` | materialized trace or seeded demand contract | Reproduce passenger arrivals and trace identity |
| `SimulationRunArtifact` | current simulator | Reproduce run configuration, policy and metrics |
| `DispatchDecisionArtifact` | decision history | Preserve controller candidate/selection evidence |
| `ExperimentArtifact` | M3 evidence | Compare repeated seeded policy experiments |
| `PolicyEvaluationArtifact` | M5/M6 evidence | Preserve held-out policy/model verdicts |
| `ModelArtifact` | M5 model JSON | Identify the fixed learned checkpoint |
| `TheoryEvidenceArtifact` | M7 evidence | Preserve discovery and falsification evidence |

Every catalog entry carries provenance keys for schema/artifact/simulator version, source, seed,
scenario, policy, configuration, creation time, trace SHA-256 and evidence source. Fields that do
not semantically apply to a committed aggregate artifact are explicitly `null` rather than
invented.

The canonical trace manifest adds metadata around the pre-existing trace digest without changing
trace identity. Its contract includes:

```text
schema_version
generator_version
seed
scenario
building_configuration
traffic_contract
duration_seconds
sha256
created_at
```

`scripts/generate_trace.py --package-dir ...` can emit:

```text
trace.json
manifest.json
schema.json
validation.json
```

The legacy trace JSON format and `PassengerTrace.digest` remain valid and unchanged.

## 6. Workbench API

Existing APIs remain available:

```text
/api/health
/api/snapshot
/api/control
/api/replay
/api/experiment
/api/theory
```

M8 adds run- and evidence-oriented endpoints:

```text
/api/runs
/api/runs/{run_id}
/api/runs/{run_id}/objects
/api/runs/{run_id}/decisions
/api/runs/{run_id}/graph
/api/runs/{run_id}/ask?question=...
/api/artifacts
/api/models
```

Run scoping makes it explicit which simulator identity an object, graph or explanation belongs to.
The additive `reset_paused` control action exists for deterministic browser/visual verification: it
atomically creates a new zero-second run and leaves it paused so tests can advance exact one-second
steps without racing the background simulation loop.

## 7. Object Explorer and Decision Trace

The object projection exposes:

```text
Elevator
Passenger
HallCall
DispatchDecision
SimulationRun
Scenario
Policy
Experiment
Model
Evidence
TheoryEvidence
```

The Decision Trace is a read-only graph projection over JSON state and ledgers. It uses React Flow
for pan/zoom/fit-view interaction and links evidence through relationships such as:

```text
Passenger ─generated→ HallCall
HallCall ─evaluated_by→ DispatchDecision
DispatchDecision ─selected→ Elevator
Elevator ─produced→ Pickup
Pickup ─contributed_to→ WaitMetric
```

Selecting graph/object evidence exposes structured data rather than hiding the source in a
visual-only graph.

## 8. Semantic ChartSpec

Analytics rendering follows:

```text
Evidence → typed ChartSpec → runtime validation → registered React renderer
```

Supported semantic specs include `TimeSeries`, `PolicyComparison`, `Distribution`,
`TradeoffScatter`, `FloorHeatmap`, `MetricCard`, `ConfidenceInterval` and `ExperimentMatrix`.

The renderer does not execute arbitrary JavaScript and does not accept arbitrary generated HTML.
Metrics must already exist in simulator/API/committed evidence contracts before a chart can render
them.

## 9. Evidence flow by workbench

### Live Operations

Uses `/api/snapshot` and the existing control/replay APIs. It preserves 18 floors, six cars, queue
state, active calls, assignment links, load, phase, route, wait/queue metrics, heatmap, decision
candidates, event stream, pause/resume/reset, scenario/policy/control-mode/speed controls and saved
replay.

### Experiments

Uses only `evidence/m3-regression-baseline.json` through `/api/experiment`, including the 30 actual
per-seed AWT observations, confidence intervals, tail metrics, fairness, energy and guardrail
classification.

### Theory

Uses `evidence/m7-bidirectional-load-sweep.json` and
`evidence/m7-threshold-validation.json`. The UI keeps both parts of the conclusion visible:

> Congestion alone is not the trigger. Continuous predictive reassignment becomes valuable when
> traffic intensity and counterflow rise together.

and:

> The threshold is fuzzy and is not a universal critical constant.

### Models

Uses `models/m5-ddqn-baseline.json` and `evidence/m5-heldout-evaluation.json`. The fixed M5 result
remains negative/mixed: `accepted_as_general_improvement` is false, with only the held-out mixed-day
mixture classified as a candidate improvement.

## 10. Ask This Run

Ask This Run is deterministic in M8:

```text
question
  ↓
bounded intent parser
  ↓
run/evidence query
  ↓
evidence package
  ↓
deterministic explanation
```

It can explain a passenger lifecycle, a recorded decision, the latest reassignment evidence, a tail
metric snapshot, or compare the current policy with collective using committed M3 evidence. The
response always returns its evidence payload and limitations. No LLM is required and an LLM is not
the source of truth.

## 11. CI and regression strategy

Every pull request runs:

```text
Python unit/contract tests
deterministic experiment smoke
destination-control smoke
artifact/trace validation
release audit
frontend npm ci
TypeScript gate
frontend unit tests
production build into web/
Playwright Chromium install
browser E2E + responsive + visual regression
```

The previous branch-name condition that limited Playwright to the M4 feature branch is removed.

The full 30-seed × six-scenario statistical regression is intentionally separated because it is
much more expensive. It runs on `main`, on the weekly schedule, or when a PR carries the
`full-statistical-regression` label. This keeps every PR fast enough to use while preserving the
release-quality evidence gate.

Visual regression targets information loss and layout regressions, not pixel-perfect design
competition. Baselines cover Live Operations desktop/mobile, Replay, Experiments, Theory, Models
and Explorer/Decision Trace. Update them intentionally with:

```bash
npm run test:e2e:update
```

## 12. Showcase capture

`npm run capture:showcase` starts/uses the same production Python server path as E2E and captures
real workbench state after browser interaction. Assets cover Live Operations after a CAPR
reassignment, Replay, Experiments, Theory, Models and Explorer/Decision Trace.

The capture is evidence of the actual product path; it is not a mock design export.

## 13. Deployment compatibility

The production contract remains:

```bash
python3 -m app.server --port 4173
```

The runtime requires Python 3.11 or newer. The macOS launchd installer validates that requirement
and prefers a supported Homebrew Python before the system `python3`, because an SSH session on the
deployment Mac can otherwise resolve the older Command Line Tools Python first.

The server continues to serve `web/` and the API from one process. M8 therefore does not require a
Node runtime on the deployed Mac mini once `web/` has been built and committed. The existing
`deploy/` service/proxy structure can continue to target the same Python command and port.

Public deployment is considered verified only after the M8 commit is actually deployed and remote
browser/API checks pass; local workbench completion alone is not treated as proof of production
deployment.

## 14. Migration strategy

The migration is deliberately incremental and backward-compatible:

1. preserve the simulator, evidence files and HTTP behavior;
2. add read-only projection contracts and tests;
3. build React/TypeScript source in parallel with the old browser implementation;
4. make Vite emit the production artifact to `web/`;
5. migrate Playwright selectors to semantic/stable selectors without reducing coverage;
6. preserve replay and API consistency before removing the old authored vanilla files;
7. generalize CI only after local Python/frontend/browser gates pass.

This makes the React migration a product-layer replacement rather than a research-core rewrite.

## 15. Reference and license policy

M8 used reference projects only within their verified license boundaries:

- **BIST reference project:** architecture/documentation/demo-automation patterns only;
- **Palantir-style local clone:** interaction architecture ideas such as shell, rail, inspector,
  split workbench and compact data presentation only; no source code copied because a root license
  was not verified;
- **team-repos/gen_data and ontology_dashboard:** artifact/provenance/CI architecture patterns only;
  no source code copied because a root license was not verified;
- **Data Formulator (MIT):** semantic chart-spec and renderer-separation ideas;
- **OpenGenerativeUI (MIT):** typed planner/spec/registered-renderer idea only; Elevator Queue Lab
  explicitly does not adopt arbitrary HTML/JavaScript execution.

## 16. Research-integrity constraints

M8 does not change the conclusions established by prior evidence:

- CAPR is not globally superior;
- the fixed M5 RL controller is not generally superior;
- the counterflow threshold is fuzzy rather than a universal critical constant;
- the demand model is synthetic and is not real-building telemetry;
- charts and explanations may only use simulator state or committed evidence;
- no browser or LLM layer may fabricate a metric or override recorded provenance.

Those constraints are product requirements, not caveats to hide from the interface.
