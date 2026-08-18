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

The canonical generator is a time-varying stochastic origin-destination process with an explicit
workplace trip-purpose mix. The default synthetic assumption is **85% lobby-linked trips, 10%
top-floor/roof-access trips and 5% same-bank inter-floor trips**. This is a modeling prior chosen to
avoid unrealistically dense floor-to-floor movement; it is not measured building telemetry.

- Morning: the 85% lobby-linked majority is 97% lobby → office up-peak.
- Lunch: the lobby-linked majority is bidirectional, slightly favoring office → lobby.
- Normal: lower-intensity traffic remains lobby-centric, with 65% of lobby-linked trips heading to 1F.
- Evening: the lobby-linked majority is 97% office → lobby down-peak.
- Roof-access: 18F is the current top-floor/roof-access proxy; roof trips stay within the high bank.
- Inter-floor: only 5% of generated trips, always within one bank because transfer journeys are not
  yet represented as multi-leg passengers.
- Shock: a 16F meeting/event release overlays the evening stream instead of inventing simultaneous
  random releases from many floors.

Every scenario must be reproducible by seed. Policy comparisons use **common random numbers**:
the same passenger trace/seed is evaluated by every policy to reduce comparison noise.

## 3. Car model

The engine models configurable floor height, maximum speed, symmetric acceleration/deceleration,
door opening/dwell/closing, passenger transfer time and capacity at a 0.25 s default simulation
step. Motion uses triangular or trapezoidal point-to-point profiles. It is still a research model:
jerk limits, manufacturer-specific leveling curves, door obstruction behavior and measured drive
energy are not yet represented and remain explicit limitations.

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

