# Elevator Queue Lab — autonomous execution contract

This repository is intended to be continued by coding agents across multiple sessions.

## Product north star

Build a research-grade, reproducible elevator group control laboratory for an 18-floor office
building with six elevators split into three low-zone and three high-zone cars. The product is
not complete when the animation looks good. It is complete when a user can reproduce traffic,
compare dispatch policies over repeated seeded simulations, inspect live passenger/elevator
state, train a policy, and generate evidence that explains whether the trained policy is better.

## Work protocol

1. Read `docs/PRODUCT_CHARTER.md`, `docs/MODELING_PROTOCOL.md`, and `docs/ROADMAP.md`.
2. Inspect open GitHub issues and choose the earliest unblocked roadmap issue.
3. Work in an isolated branch/worktree for parallel tasks.
4. Do not replace the simulator with hard-coded chart data. UI values must come from the engine.
5. Preserve deterministic seeded runs. Any stochastic feature must accept a seed.
6. Add or update tests for every model/policy change.
7. Run `python -m unittest discover -s tests -v` and the experiment smoke test before push.
8. Update roadmap evidence only after the acceptance criteria are actually met.
9. Never claim a learned controller is superior from a single seed. Use the experiment protocol.
10. Keep standards/research references as inspiration and validation targets; do not claim formal
    ISO/CIBSE compliance without implementing and auditing the relevant normative requirements.

## Definition of done

The final release must satisfy all of the following:

- deterministic discrete-event or sub-second simulation with configurable building/car physics;
- time-varying office origin-destination demand for morning, lunch, normal, evening and shock load;
- conventional hall-call and destination-control experiments;
- baseline, collective, queue-aware, predictive-reassignment and learned controllers;
- capacity-full pass and reassignment latency represented explicitly;
- Monte Carlo comparison across at least 30 seeds with confidence intervals;
- AWT, P50/P95/P99 wait, time-to-destination, queue length, throughput, capacity misses,
  reassignment latency, floor fairness and energy proxy metrics;
- live browser digital twin plus experiment comparison and replay;
- saved experiment artifacts (`json/csv`) and a generated research report;
- CI tests and a deployable public demo;
- README containing architecture, methodology, limitations and reproducible results.

