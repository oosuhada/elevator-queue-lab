# Elevator Queue Lab

**A reproducible elevator group-control research lab for an 18-floor office building.**

Elevator Queue Lab starts from a practical failure mode: a hall call is assigned to a car, that
car later becomes full or follows a poor route, and the passenger waits while the controller keeps
treating the stale assignment as valid. The project turns that observation into a controlled
simulation and optimization problem.

The target building has **18 floors and six passenger elevators**: three low-zone cars and three
high-zone cars. Synthetic office traffic changes through morning arrival, lunch inter-floor flow,
normal traffic and evening departure. Every passenger is represented from arrival at a hall call
through boarding and destination arrival, so dispatch decisions can be evaluated on passenger
outcomes instead of visual car movement alone.

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
- live digital-twin view of floors, cars, queues, load, assignments, wait metrics and CAPR decisions;
- 30-seed common-random-number experiment engine with morning/lunch/normal/evening/shock/mixed-day;
- P50/P95/P99 wait, journey time, throughput, unfinished queue, reassignment latency, floor fairness,
  capacity misses and a transparent comparative energy proxy;
- JSON + run-level CSV + summary CSV evidence artifacts, paired effect sizes and guardrail flags;
- checked-in statistical regression baseline enforced by GitHub Actions.

## First 30-seed evidence: CAPR is regime-dependent

The first M3 matrix runs **30 seeds × 6 scenarios × 5 policies = 900 controller simulations** with
the same passenger trace for every policy at a given seed. It deliberately does not produce a
single global winner.

- **Lunch:** CAPR is a clean candidate improvement: collective mean wait **24.15 s → 22.16 s** while
  the configured tail/fairness/energy guardrails remain within tolerance.
- **Normal:** CAPR improves mean wait **16.18 s → 12.04 s** and P95 **42.52 s → 26.81 s**, but the
  energy proxy rises **424 → 1122**, so the result is classified as a tradeoff rather than a win.
- **Mixed day:** CAPR strongly reduces wait (**50.26 s → 14.66 s**) but roughly doubles the energy
  proxy (**858 → 1734**), again triggering the energy guardrail.
- **Morning / evening / shock:** current CAPR does not beat collective on mean wait.
- **Morning:** the simpler nearest-car baseline is the strongest unconditional candidate in this
  short-window benchmark, useful evidence against forcing the project narrative toward CAPR.

See `docs/M3_FINDINGS.md` for the full interpretation and limitations. These are reproducible
simulation results, **not real-building performance claims**.

## Run locally

Python 3.11+ is enough for the current simulator/controller lab.

```bash
python -m app.server --port 4173
```

Open `http://127.0.0.1:4173`. The live UI can switch traffic regime, policy, simulation speed, and
conventional versus destination-control call input.

Run validation and evidence generation:

```bash
python -m unittest discover -s tests -v
python scripts/generate_trace.py --scenario evening --seconds 600 --seed 7 --output /tmp/evening-trace.json
python scripts/run_experiment.py --scenario evening --seconds 600 --seeds 3
python scripts/run_experiment.py --scenario evening --seconds 600 --seeds 3 --control-mode destination
python scripts/run_experiment.py --matrix --seconds 180 --seeds 30 --output evidence/m3-evidence.json
python scripts/check_regression_baseline.py evidence/m3-evidence.json
```

The matrix command emits a self-describing JSON artifact plus `*.runs.csv` and `*.summary.csv`.
Artifacts explicitly record a zero-second warm-up and the measurement window used by the run.

## Project status

**M0 reproducibility, M1 simulator physics, M2 controller laboratory and M3 statistical evidence
engine are implemented.** The next milestone is M4: turn the current live simulator into a
release-quality digital twin with experiment comparison, heatmaps and deterministic replay.
`docs/ROADMAP.md` is the canonical work queue and `AGENTS.md` defines the continuation contract for
future coding sessions.

## Methodology references

The modeling plan is informed by ISO 8100-32 traffic-planning concepts, CIBSE Guide D lift traffic
simulation/control topics, and current elevator group-control research. This project does **not**
claim formal standards compliance. See `docs/MODELING_PROTOCOL.md` for scope and limitations.

## License

MIT, unless a later dependency or imported dataset requires a narrower notice.
