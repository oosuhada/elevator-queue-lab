# Elevator Queue Lab

**A reproducible elevator group-control research lab for an 18-floor office building.**

**Live demo:** [https://elevator.oosu.dev/](https://elevator.oosu.dev/)

Elevator Queue Lab starts from a practical failure mode: a hall call is assigned to a car, that
car later becomes full or follows a poor route, and the passenger waits while the controller keeps
treating the stale assignment as valid. The project turns that observation into a controlled
simulation and optimization problem.

The target building has **18 floors and six passenger elevators**: three low-zone cars and three
high-zone cars. The default synthetic workplace mix is deliberately lobby-centric: **85% of trips
touch 1F, 10% use 18F as a roof-access proxy and only 5% are same-bank inter-floor trips**. Time of
day changes the direction of that mix rather than inventing dense floor-to-floor traffic. Every
passenger is represented from arrival at a hall call
through boarding and destination arrival, so dispatch decisions can be evaluated on passenger
outcomes instead of visual car movement alone.

![Elevator Queue Lab live digital twin](docs/assets/m6-dashboard.png)

The screenshot above is captured from the deployed public simulator at `elevator.oosu.dev` after
Chromium verifies the live UI/API contract: all six cars, all 18 floors, the evidence cards, the
learned-policy control path and simulator audit. It is not a mockup or static chart fixture.

> **Research takeaway — congestion alone is not the trigger.** Continuous predictive reassignment
> becomes valuable when **heavy traffic and enough counterflow rise together**, because opposing
> directional demand makes stale assignments increasingly costly to keep. In practical terms:
> **do not reassign just because the system is busy; reassign when directional competition is high
> enough to justify the churn.** The M7 controlled sweep and held-out falsification below quantify
> this as the Counterflow Criticality Hypothesis.

## Research question

> Can continuous capacity-aware reassignment and demand-aware pre-positioning reduce both average
> and tail waiting time in a zoned six-car office elevator group without creating unacceptable
> energy use or floor-level unfairness?

The working controller family is **CAPR — Capacity-Aware Predictive Reassignment**. CAPR estimates
route-insertion pickup ETA and residual capacity, continuously re-evaluates an assignment,
invalidates a predicted-full car before the failed pickup, and uses hysteresis to prevent
reassignment oscillation. It remains a **hypothesis to test, not a claim of novelty or universal
superiority**.

## Current executable surface

- deterministic origin/destination passenger traces with canonical JSON + SHA-256 identity;
- sub-second six-car simulator with acceleration/deceleration, doors and passenger transfer time;
- low/high zoned banks and both conventional hall-call and destination-control grouping;
- sticky, nearest-car, collective, queue-aware and CAPR dispatch policies;
- route-insertion ETA, predicted pickup capacity, call-age scoring and demand-aware parking;
- assignment/reassignment decision ledger containing candidate scores and human-readable reasons;
- regression coverage for the motivating **17F full car / 16F waiting passenger** case;
- portfolio-grade 18-floor live digital twin with car phase/load/route, queue badges and assignment links;
- floor queue heatmap plus live/replay wait and queue time series sourced only from simulator state;
- dispatch event stream and candidate-level decision inspector for assignment/reassignment reasoning;
- deterministic saved-run replay with a timeline scrubber and live/replay state switching;
- 30-seed common-random-number experiment engine with morning/lunch/normal/evening/shock/mixed-day;
- P50/P95/P99 wait, journey time, throughput, unfinished queue, reassignment latency, floor fairness,
  capacity misses and a transparent comparative energy proxy;
- M3 decision dashboard backed by the checked-in regression evidence baseline: guardrail-aware
  policy ranking, raw speed rank, 95% CI/tail/fairness/energy table and a KDE over the 30 actual
  per-seed average-wait observations for each dispatch policy;
- M7 counterflow-criticality panel backed by a CAPR-vs-CAPR-static ablation, controlled λ/p phase
  sweep and an unseen-grid falsification run rather than hand-entered theory claims;
- Gymnasium-compatible M5 dispatch MDP with a 77-value observation, seven masked actions and an
  explicit wait/tail/fairness/capacity/energy reward contract;
- dependency-free Dueling Double DQN learned policy, checked-in model artifact and deterministic
  train/held-out evaluation command;
- `rl` runtime policy selectable in the live digital twin using the checked-in M5 model;
- JSON + run-level CSV + summary CSV evidence artifacts, paired effect sizes and guardrail flags;
- Playwright browser verification that visible metrics, all six cars and all 18 floor queues match API/replay state;
- responsive desktop/mobile visual QA with screenshots generated from that same verified browser run.

## 30-seed evidence: CAPR is regime-dependent

The first M3 matrix runs **30 seeds × 6 scenarios × 5 policies = 900 controller simulations** with
the same passenger trace for every policy at a given seed. It deliberately does not produce a
single global winner.

- **Lunch:** CAPR is a clean candidate improvement: collective mean wait **24.84 s → 21.77 s** while
  the configured tail/fairness/energy guardrails remain within tolerance.
- **Morning:** CAPR improves collective **35.70 s → 24.45 s**, but energy rises **801 → 1005**;
  simpler sticky/nearest baselines are faster still, so CAPR is not the right default here.
- **Normal:** CAPR improves mean wait **18.12 s → 11.48 s** and P95 **49.59 s → 25.38 s**, but the
  energy proxy rises **524 → 1113**, so the result remains a tradeoff.
- **Mixed day:** CAPR strongly reduces wait (**39.32 s → 15.20 s**) but energy rises **893 → 1711**.
- **Evening / shock:** current CAPR does not beat collective on mean wait in the M3 baseline.

See `docs/M3_FINDINGS.md` for the full interpretation and limitations. These are reproducible
simulation results, **not real-building performance claims**.

## M7 theory candidate: counterflow criticality

**Key takeaway:** “reassign under congestion” is too crude. The evidence instead supports a
**congestion × counterflow** rule: stale-assignment correction becomes materially more valuable only
when traffic intensity and opposing directional flow are both high enough. That distinction explains
why the project sees a low-churn morning regime (`B = 2.56`) but a predictive-reassignment lunch
regime (`B = 15.84`) even though both can be busy office periods.

The scenario-level result suggested a deeper question: why is predictive reassignment useful in
lunch-like traffic but wasteful in strongly one-way peaks? M7 isolates that mechanism with
`capr_static`, which uses the same CAPR scoring and parking logic while disabling only continuous
reconsideration of already-owned calls.

Across **40 controlled traffic cells × 30 seeds × 3 policies = 3,600 discovery runs**, a normalized
bidirectional-load index

`B = λ × 4p↑(1 − p↑)`

tracks the marginal CAPR reassignment effect: discovery correlation with CAPR-minus-static average
wait is **r = −0.748**. Low-B cells show reassignment churn; high-B cells increasingly benefit from
predictive ownership changes. A strict 95%-CI gain trigger near **B ≈ 12.33** classifies 87.5% of
the discovery grid.

The trigger was frozen and tested on **18 unseen λ/p cells × 30 seeds = 1,080 additional
paired-policy runs**. Accuracy drops to **72.2%**, so the repository explicitly rejects a hard
universal critical-constant claim. It still captures every held-out CI-supported gain, and the
continuous discovery equation generalizes with held-out effect correlation **r = 0.672** and
**0.805 s MAE**.

Applying the frozen B trigger as an offline selector on those held-out cells keeps **88.1% of the
always-on CAPR wait gain while reducing CAPR's additional energy overhead by 58.3%**. This makes the
candidate theory operational: richer reassignment may be best treated as a gated intervention,
not a permanently active feature.

The current result is therefore a **Counterflow Criticality Hypothesis**: continuous predictive
reassignment appears to undergo a fuzzy transition from churn to useful intervention as directional
competition and traffic intensity increase together. It is a project-specific empirical theory to
falsify on other building sizes, capacities and trip-purpose mixes—not a claimed universal theorem
or established algorithmic novelty. See
[`docs/M7_COUNTERFLOW_CRITICALITY.md`](docs/M7_COUNTERFLOW_CRITICALITY.md).

![M7 counterflow criticality discovery and held-out validation](docs/assets/m7-counterflow-criticality.svg)

## First held-out learned-controller evidence: negative/mixed

M5 deliberately uses disjoint data: the model trains on passenger seeds **1–6** across five base
traffic regimes, while evaluation uses seeds **21–30**. `mixed_day` is excluded from training and
serves as the held-out traffic mixture. Collective, CAPR and RL see the same passenger trace for
each held-out scenario/seed.

- **Morning:** collective 34.16 s mean wait vs RL 42.24 s.
- **Lunch:** 22.47 s vs RL 34.79 s.
- **Normal:** 17.50 s vs RL 22.83 s.
- **Evening:** 20.69 s vs RL 34.76 s.
- **Shock:** 21.84 s vs RL 35.08 s.
- **Held-out mixed day:** collective 37.72 s vs RL 35.72 s; this is the only M5 scenario classified
  as a guardrail-clean candidate improvement.

So the checked-in Dueling Double DQN **does not pass the general-superiority gate**. Five traffic
regimes regress on mean wait; the one mixed-day improvement is not enough to declare a general RL
win. ETA/load/capacity/age/pre-positioning feature ablations do not overturn that conclusion.
See `docs/M5_MODEL_CARD.md` and `evidence/m5-heldout-evaluation.json`.

## Final 30-seed held-out release evidence

M6 keeps the exact retrained M5 checkpoint fixed and expands the release evaluation to **30 disjoint
held-out passenger seeds (21–50)**. The overall conclusion is unchanged: CAPR is a clean candidate
only in lunch traffic, while morning/normal/evening/shock/mixed traffic all expose either no gain or
a service/energy trade-off; the RL
checkpoint improves only the unseen `mixed_day` mixture and is not a general replacement for the
heuristic controllers.

![30-seed held-out mean waiting time](docs/assets/m6-heldout-wait.svg)

![Wait-energy trade-off versus collective](docs/assets/m6-wait-energy-tradeoff.svg)

The strongest supported operating rule is therefore **regime-gated predictive intervention with
tail/fairness/energy vetoes**, not “always CAPR” and not “always RL.” See
`docs/M6_RESEARCH_REPORT.md` for the architecture, evidence interpretation, external references and
limitations, and `docs/M6_EVIDENCE_SUMMARY.md` for tables generated directly from committed JSON.

## Run locally

Python 3.11+ is enough for the simulator and research server.

```bash
python -m app.server --port 4173
```

Open `http://127.0.0.1:4173`. The UI can switch traffic regime, policy, simulation speed and
conventional versus destination-control call input, save the current run, scrub deterministic
replay frames and inspect the M3 comparison evidence.

Run validation and evidence generation:

```bash
python -m unittest discover -s tests -v
python scripts/generate_trace.py --scenario evening --seconds 600 --seed 7 --output /tmp/evening-trace.json
python scripts/run_experiment.py --scenario evening --seconds 600 --seeds 3
python scripts/run_experiment.py --scenario evening --seconds 600 --seeds 3 --control-mode destination
python scripts/run_experiment.py --matrix --seconds 180 --seeds 30 --output evidence/m3-evidence.json
python scripts/check_regression_baseline.py evidence/m3-evidence.json
python scripts/run_m5_training.py
python scripts/run_m6_evaluation.py
python scripts/generate_m6_assets.py
python scripts/audit_release.py
```

For browser/API visual verification:

```bash
npm install
npx playwright install chromium
python -m app.server --port 4173
npm run test:e2e
```

The matrix command emits a self-describing JSON artifact plus `*.runs.csv` and `*.summary.csv`.
Artifacts explicitly record a zero-second warm-up and the measurement window used by the run.

## Project status

**M0 reproducibility through M6 portfolio release are implemented.** The fixed M5 checkpoint has a
30-seed held-out release artifact, the final report/plots are generated from committed evidence,
and the public Mac mini deployment is live at `https://elevator.oosu.dev/`. External Chromium QA
verifies HTTP 200, six cars, all 18 floors, five evidence cards, the RL `mixed_day` control path,
simulator audit success, zero failed browser requests and zero console errors.
`docs/ROADMAP.md` is the canonical work queue and `AGENTS.md` defines the continuation contract for
future coding sessions.

## Methodology references

The modeling plan is informed by ISO 8100-32 traffic-planning concepts, CIBSE Guide D lift traffic
simulation/control topics, and current elevator group-control research. This project does **not**
claim formal standards compliance. See `docs/MODELING_PROTOCOL.md` for scope and limitations.

## License

MIT, unless a later dependency or imported dataset requires a narrower notice.
