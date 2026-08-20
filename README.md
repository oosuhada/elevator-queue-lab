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

The working controller family is **CAPR — Capacity-Aware Predictive Reassignment**. CAPR is now an
executable, explainable controller: it estimates route-insertion pickup ETA and residual capacity,
continuously re-evaluates an assignment, invalidates a predicted-full car before the failed pickup,
and uses hysteresis to prevent reassignment oscillation. It remains a **hypothesis to test, not a
claim of novelty or superiority**. A learned controller will later challenge the hand-designed
policies under the same deterministic passenger traces.

## Current executable surface

- deterministic origin/destination passenger traces with canonical JSON + SHA-256 identity;
- sub-second six-car simulator with acceleration/deceleration, doors and passenger transfer time;
- low/high zoned banks and both conventional hall-call and destination-control grouping;
- sticky, nearest-car, collective, queue-aware and CAPR dispatch policies;
- route-insertion ETA, predicted pickup capacity, call-age scoring and demand-aware parking;
- assignment/reassignment decision ledger containing candidate scores and human-readable reasons;
- regression coverage for the motivating **17F full car / 16F waiting passenger** case;
- live digital-twin view of floors, cars, queues, load, assignments, wait metrics and CAPR decisions;
- deterministic experiment runner using identical passenger traces across policies.

## Early result — deliberately not a victory claim

A short 180-second, two-seed evening smoke experiment is a software regression check, not research
evidence. In that small run, collective control still produced lower mean wait than CAPR. CAPR's
first implementation also exposed a reassignment-thrashing defect; hysteresis reduced the observed
smoke-run reassignment rate from **211.5 to 21.0 per run pair average** while preserving the
pre-full-car invalidation regression. These negative/intermediate results stay visible on purpose.
The M3 experiment engine will decide performance using 30+ common-random-number seeds, tail latency,
fairness, capacity and energy guardrails rather than a favorable cherry-picked run.

## Run locally

Python 3.11+ is enough for the current simulator/controller lab.

```bash
python -m app.server --port 4173
```

Open `http://127.0.0.1:4173`. The live UI can switch traffic regime, policy, simulation speed, and
conventional versus destination-control call input.

Run validation:

```bash
python -m unittest discover -s tests -v
python scripts/generate_trace.py --scenario evening --seconds 600 --seed 7 --output /tmp/evening-trace.json
python scripts/run_experiment.py --scenario evening --seconds 600 --seeds 3
python scripts/run_experiment.py --scenario evening --seconds 600 --seeds 3 --control-mode destination
```

## Project status

**M0 reproducibility, M1 simulator physics and M2 controller laboratory are implemented.** M3 is the
next gate: a release-quality Monte Carlo/statistical evidence engine. `docs/ROADMAP.md` is the
canonical work queue and `AGENTS.md` defines the continuation contract for future coding sessions.

## Methodology references

The modeling plan is informed by ISO 8100-32 traffic-planning concepts, CIBSE Guide D lift traffic
simulation/control topics, and current elevator group-control research. This project does **not**
claim formal standards compliance. See `docs/MODELING_PROTOCOL.md` for scope and limitations.

## License

MIT, unless a later dependency or imported dataset requires a narrower notice.
