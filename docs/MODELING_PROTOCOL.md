# Modeling and experiment protocol

## 1. Why simulation

Elevator group control is state-dependent: travel time, route commitments, passenger arrivals,
capacity, door cycles and future calls interact. Closed-form queue formulas are useful diagnostics,
but a passenger-level simulation is the primary experiment mechanism.

ISO 8100-32:2020 explicitly includes simulation as a lift traffic planning method for office,
hotel and residential installations. The 2025 CIBSE Guide D separates calculation, simulation,
traffic control, energy and data topics. These references motivate the dimensions we expose; this
open project is not a normative implementation of either publication.

## 2. Demand model

The canonical generator is a time-varying stochastic origin-destination process.

- Morning: lobby-dominant arrivals with smaller inter-floor traffic.
- Lunch: office-to-lobby and lobby-to-office waves plus inter-floor movement.
- Normal: lower mixed flow.
- Evening: office-to-lobby dominant down-peak.
- Shock: a meeting/event release producing a temporary floor hotspot.

Every scenario must be reproducible by seed. Policy comparisons use **common random numbers**:
the same passenger trace/seed is evaluated by every policy to reduce comparison noise.

## 3. Car model

The engine must eventually model configurable speed, acceleration, deceleration, door opening,
dwell/closing, passenger transfer time and capacity. The current foundation uses simplified
per-floor movement and fixed dwell and is therefore marked as a model limitation until the
kinematic milestone lands.

## 4. Controller baselines

1. `legacy_sticky`: intentionally delayed reassignment; reproduces the motivating failure mode.
2. `collective`: direction-aware collective control heuristic.
3. `queue_aware`: ETA/load/route-aware scoring with immediate failed-pickup reassignment.
4. `capr`: predictive capacity and assignment invalidation (roadmap).
5. `rl`: learned controller using the same state/action constraints (roadmap).

## 5. Metrics

Primary passenger metrics:

- average waiting time (AWT / Wq);
- median, P95 and P99 waiting time;
- time to destination (waiting + ride);
- throughput and unfinished passengers;
- full-car pickup misses;
- assignment and reassignment latency;
- worst-floor and floor-percentile waiting time.

System metrics:

- average/max queue length;
- car utilization and load distribution;
- starts/stops and traveled distance;
- energy proxy until a validated physical energy model is implemented.

Little's Law (`Lq ≈ λWq`) is displayed as a diagnostic check over suitably stable windows, not as a
claim that the entire elevator system is an M/M/c queue.

## 6. Statistical comparison

For a release-quality benchmark:

- warm-up period documented per scenario;
- at least 30 common seeds;
- equal scenario duration and arrival traces per policy;
- mean plus bootstrap or t-based 95% confidence intervals;
- effect size relative to baseline;
- per-scenario and pooled reporting;
- explicit failure cases when a policy improves mean but worsens tail/fairness/energy.

## 7. Learning roadmap

The first optimization is transparent heuristic weight search to validate the experiment loop.
The learning milestone then exposes the simulator as an MDP with bounded actions and trains a
Dueling Double DQN-style controller, inspired by recent EGCS research. A learned result is accepted
only if it generalizes to held-out seeds and at least one held-out traffic mixture.

