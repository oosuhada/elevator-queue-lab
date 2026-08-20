# Elevator Queue Lab

**A reproducible elevator group-control research lab for an 18-floor office building.**

Elevator Queue Lab starts from a very practical failure mode: a hall call is assigned to a car,
that car later becomes full or follows a poor route, and the passenger waits while the controller
continues to treat the stale assignment as valid. The project turns that observation into a
controlled simulation and optimization problem.

The target building has **18 floors and six passenger elevators**: three low-zone cars and three
high-zone cars. Synthetic office traffic changes through morning arrival, lunch inter-floor flow,
normal traffic and evening departure. Every passenger is represented from arrival at a hall call
through boarding and destination arrival, so dispatch decisions can be evaluated on passenger
outcomes instead of visual car movement alone.

## Research question

> Can continuous capacity-aware reassignment and demand-aware pre-positioning reduce both average
> and tail waiting time in a zoned six-car office elevator group without creating unacceptable
> energy use or floor-level unfairness?

The working controller family is **CAPR — Capacity-Aware Predictive Reassignment**. It is a
hypothesis to test, not a claim of novelty. A learned controller will later optimize and challenge
the hand-designed policies under the same deterministic traffic traces.

## What the finished project contains

- a seeded passenger demand generator with explicit origin/destination traffic;
- elevator car kinematics, door dwell, capacity, routes and bank constraints;
- multiple dispatch policies, including a deliberately sticky baseline;
- explicit full-car pass and delayed/immediate reassignment behavior;
- live digital-twin visualization of floors, queues, cars, loads and assignments;
- queue metrics including `Wq`, tail wait, `Lq`, throughput and Little's Law diagnostics;
- repeatable Monte Carlo policy comparisons;
- policy parameter search, followed by an RL environment/controller milestone;
- saved experiment artifacts and generated evidence for the README/report.

## Run locally

Python 3.11+ is enough for the current foundation.

```bash
python -m app.server --port 4173
```

Open `http://127.0.0.1:4173`.

Run validation:

```bash
python -m unittest discover -s tests -v
python scripts/run_experiment.py --scenario evening --seconds 600 --seeds 3
```

## Project status

The repository is being built milestone-by-milestone. The executable simulator foundation is in
place; `docs/ROADMAP.md` is the canonical work queue and `AGENTS.md` defines the continuation
contract for future coding sessions.

## Methodology references

The modeling plan is informed by ISO 8100-32 traffic-planning concepts, CIBSE Guide D lift traffic
simulation/control topics, and current elevator group-control research. This project does **not**
claim formal standards compliance. See `docs/MODELING_PROTOCOL.md` for scope and limitations.

## License

MIT, unless a later dependency or imported dataset requires a narrower notice.

