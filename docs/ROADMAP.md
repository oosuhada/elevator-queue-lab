# Execution roadmap

This file is the canonical milestone order. GitHub issues mirror these items so another coding
session can immediately continue from the first open, unblocked issue.

## M0 — research contract and reproducible foundation

- [x] define target building, hypotheses, metrics and non-goals;
- [x] seeded office demand generator;
- [x] six-car zoned simulation foundation;
- [x] initial sticky/collective/queue-aware policies;
- [x] deterministic trace export/import so every controller sees identical passengers;
- [x] event ledger for arrival/assign/reassign/board/alight/full-pass actions.

**Gate:** same seed must yield byte-equivalent demand trace; event counts must reconcile with
passenger lifecycle counts.

## M1 — physically credible simulator

- [x] sub-second clock with acceleration/deceleration and door phase model;
- [x] per-passenger boarding/alighting transfer time;
- [x] configurable capacities, floor heights, speed and bank topology;
- [x] abandonment/patience option kept off by default;
- [x] invariant/property tests for impossible trips, negative waits and capacity overflow.

**Gate:** simulation invariants pass 100 seeded stress runs.

## M2 — controller laboratory

- [x] nearest-car and conventional collective baselines;
- [x] route-insertion ETA estimator;
- [x] CAPR predictive residual-capacity model;
- [x] continuous reassignment with hysteresis to prevent thrashing;
- [x] anti-starvation call-age term;
- [x] demand-aware parking/pre-positioning;
- [x] destination-control mode.

**Gate:** every assignment decision records candidate scores and a human-readable reason. The
controller also has regression coverage for the motivating 17F-full / 16F-waiting case, all-full
ownership stability and non-capacity reassignment budgeting. M2 establishes a testable controller;
it does not claim CAPR is superior. Statistical superiority belongs to M3.

## M3 — experiment and statistics engine

- [x] 30+ seed common-random-number Monte Carlo runner;
- [x] confidence intervals/effect sizes;
- [x] P50/P95/P99, journey time, fairness, capacity miss, reassignment latency and energy proxy;
- [x] scenario matrix: morning/lunch/normal/evening/shock/mixed day;
- [x] JSON/CSV experiment artifacts and checked-in regression baseline.

**Gate:** one command creates a complete policy-comparison artifact with explicit zero-warm-up /
measurement-window metadata, identical per-seed traces, paired effect sizes and guardrail
classification. CI executes the 30-seed × 6-scenario × 5-policy matrix and compares headline metrics
and trace manifests against `evidence/m3-regression-baseline.json`. See `docs/M3_FINDINGS.md` for the
first evidence interpretation; CAPR is traffic-regime dependent rather than globally superior.

## M4 — live digital twin and replay

- [x] 18-floor animated building, six cars and passenger queues;
- [x] live assignment/reassignment links and capacity-pass visualization;
- [x] wait/queue time series and floor heatmap;
- [x] experiment comparison screen sourced from the M3 evidence baseline;
- [x] deterministic saved-run replay with scrubber;
- [x] decision inspector and dispatch event stream;
- [x] responsive visual QA and committed screenshot evidence.

**Gate:** no chart uses fabricated values. Playwright runs a real shock/CAPR simulation through a
predictive reassignment, pauses it, compares visible clock/queue/wait metrics, all six cars, active
calls/assignment links, decision candidates and all 18 floor queue cells against `/api/snapshot`,
saves the run, then repeats the comparison against `/api/replay`. Desktop and
390px mobile screenshots come from that verified browser run; the desktop image is preserved at
`docs/assets/m4-dashboard.png` for README visual QA.

## M5 — learned control

- [x] Gymnasium-compatible MDP environment;
- [x] state/action/reward contract and masking for infeasible actions;
- [x] Dueling Double DQN baseline;
- [x] held-out seed/scenario evaluation;
- [x] ablation versus CAPR terms;
- [x] model artifact + model card + reproducible training command.

**Gate:** learned policy improvement must survive held-out evaluation and not violate fairness or
energy guardrails. Otherwise the report explicitly records the negative result. The first fixed
M5 checkpoint does **not** pass this superiority gate: held-out seeds 21–30 show a guardrail-clean
improvement only on the completely held-out `mixed_day` mixture, while morning/lunch/normal/
evening/shock all fail the collective mean-wait comparison. See `docs/M5_MODEL_CARD.md` and
`evidence/m5-heldout-evaluation.json`.

## M6 — theory extraction and portfolio release

- [x] analyze which CAPR/RL terms correlate with gains by traffic regime without overstating causality;
- [x] formulate the strongest supported dispatch rule/theory with limitations;
- [x] generate final plots and experiment tables from committed evidence;
- [x] write research report and architecture diagram;
- [x] run a fixed-checkpoint 30-seed held-out release evaluation disjoint from M5 training;
- [x] refresh the README screenshot from the current real simulator UI and pass local browser QA;
- [x] add and pass an executable clean-repository release audit;
- [x] prepare an isolated `elevator.oosu.dev` Mac mini service/proxy deployment path;
- [x] deploy the dedicated public demo at `https://elevator.oosu.dev/`;
- [x] run public health/Chromium QA and verify the README live-demo link.

**Gate:** a reviewer can clone, reproduce one benchmark, understand the hypothesis and open a live
demo without private infrastructure.

## Post-release hardening — office demand realism v2

- [x] replace over-mixed floor-to-floor demand with an explicit 85% lobby / 10% roof / 5% inter-floor contract;
- [x] make lobby direction regime-aware instead of changing the trip-purpose mix;
- [x] constrain roof/inter-floor trips to physically feasible banks and make shock traffic a 16F event release;
- [x] embed the demand contract in M3/M5/M6 evidence and regression checks;
- [x] regenerate the 900-run M3 baseline, retrain M5, and rerun the M6 30-seed held-out release;
- [ ] deploy and visually re-verify the hardened demand model at `https://elevator.oosu.dev/`.
