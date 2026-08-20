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
