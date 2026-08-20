# Execution roadmap

This file is the canonical milestone order. GitHub issues mirror these items so another coding
session can immediately continue from the first open, unblocked issue.

## M0 — research contract and reproducible foundation

- [x] define target building, hypotheses, metrics and non-goals;
- [x] seeded office demand generator;
- [x] six-car zoned simulation foundation;
- [x] initial sticky/collective/queue-aware policies;
- [ ] deterministic trace export/import so every controller sees identical passengers;
- [ ] event ledger for arrival/assign/reassign/board/alight/full-pass actions.

**Gate:** same seed must yield byte-equivalent demand trace; event counts must reconcile with
passenger lifecycle counts.

## M1 — physically credible simulator

- [ ] discrete-event clock with acceleration/deceleration and door phase model;
- [ ] per-passenger boarding/alighting transfer time;
- [ ] configurable capacities, floor heights, speed and bank topology;
- [ ] abandonment/patience option kept off by default;
- [ ] invariant/property tests for impossible trips, negative waits and capacity overflow.

**Gate:** simulation invariants pass 100 seeded stress runs.

## M2 — controller laboratory

- [ ] nearest-car and conventional collective baselines;
- [ ] route-insertion ETA estimator;
- [ ] CAPR predictive residual-capacity model;
- [ ] continuous reassignment with hysteresis to prevent thrashing;
- [ ] anti-starvation call-age term;
- [ ] demand-aware parking/pre-positioning;
- [ ] destination-control mode.

**Gate:** every assignment decision records candidate scores and a human-readable reason.

## M3 — experiment and statistics engine

- [ ] 30+ seed common-random-number Monte Carlo runner;
- [ ] confidence intervals/effect sizes;
- [ ] P50/P95/P99, journey time, fairness, capacity miss and energy proxy;
- [ ] scenario matrix: morning/lunch/normal/evening/shock/mixed day;
- [ ] JSON/CSV experiment artifacts and regression baseline.

**Gate:** one command creates a complete policy-comparison artifact with reproducible metadata.

## M4 — live digital twin and replay

- [ ] 18-floor animated building, six cars and passenger queues;
- [ ] live assignment/reassignment links and capacity-pass visualization;
- [ ] metrics time series and floor heatmap;
- [ ] experiment comparison screen;
- [ ] deterministic saved-run replay with scrubber;
- [ ] responsive visual QA and screenshot evidence.

**Gate:** no chart uses fabricated values; a browser test verifies visible state against API state.

## M5 — learned control

- [ ] Gymnasium-compatible MDP environment;
- [ ] state/action/reward contract and masking for infeasible actions;
- [ ] Dueling Double DQN baseline;
- [ ] held-out seed/scenario evaluation;
- [ ] ablation versus CAPR terms;
- [ ] model artifact + model card + reproducible training command.

**Gate:** learned policy improvement must survive held-out evaluation and not violate fairness or
energy guardrails. Otherwise the report explicitly records the negative result.

## M6 — theory extraction and portfolio release

- [ ] analyze which CAPR/RL terms cause gains by traffic regime;
- [ ] formulate the strongest supported dispatch rule/theory with limitations;
- [ ] generate final plots and experiment tables;
- [ ] write research report and architecture diagram;
- [ ] deploy public demo;
- [ ] README visual QA, demo QA and clean repository audit.

**Gate:** a reviewer can clone, reproduce one benchmark, understand the hypothesis and open a live
demo without private infrastructure.

