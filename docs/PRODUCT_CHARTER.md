# Product charter

## 1. Problem

Real elevator group control is a stochastic scheduling problem. A choice that looks locally good
can become bad after new passengers arrive, a car fills at another floor, or a route gains stops.
The motivating failure case is **assignment stickiness**: a passenger remains logically assigned
to a car that is no longer a good pickup candidate, and reassignment happens only after the bad
outcome is observed.

## 2. Exact target system

- Building: 18 occupied floors, lobby at 1F.
- Cars: 6 total.
- Low bank: L1–L3, lobby + 2F–9F.
- High bank: H1–H3, lobby + 10F–18F.
- Default nominal capacity: 14 passengers/car, configurable.
- Traffic regimes: morning up-peak, lunch mixed, normal mixed, evening down-peak, demand shock.
- Passenger model: individual origin, destination, arrival, assignment, boarding and arrival times.
- Control modes: conventional direction hall calls first; destination control as a later milestone.

The observed real building motivates the configuration, but no claim is made that its proprietary
controller, timing constants or exact capacity are known. Unknown parameters remain configurable.

## 3. Research hypotheses

### H1 — stale assignment penalty

Controllers that keep a hall-call assignment after predicted residual capacity becomes inadequate
produce longer P95/P99 waits and more repeated capacity misses during down-peak traffic.

### H2 — continuous reassignment

Re-evaluating assigned calls when route/load state changes reduces tail waiting time compared with
reassignment only after a failed pickup.

### H3 — demand-aware parking

Pre-positioning idle cars toward forecast demand hotspots reduces pickup delay in strongly
directional periods, but can increase movement/energy proxy under normal traffic.

### H4 — learned policy

A learned policy can beat fixed heuristic weights across mixed traffic only if the objective also
penalizes starvation/fairness and energy; optimizing mean wait alone will create pathological
behavior in some floors or regimes.

## 4. Candidate controller: CAPR

**Capacity-Aware Predictive Reassignment (CAPR)** continuously scores each feasible car using:

1. predicted pickup ETA rather than geometric distance;
2. predicted residual capacity at the pickup floor;
3. route insertion cost and number of committed stops;
4. direction compatibility;
5. age of the hall call, with increasing anti-starvation weight;
6. short-horizon demand forecast for parking/repositioning.

An assignment becomes invalid when a better feasible car exceeds a configurable improvement
threshold or the assigned car is predicted to arrive without enough capacity. This is the main
theory candidate the experiments will try to support, reject or refine.

## 5. Success criteria

The project reaches portfolio-complete status only when:

1. all final `AGENTS.md` definition-of-done bullets are met;
2. benchmark runs use at least 30 common random-number seeds per policy;
3. the final report includes confidence intervals and per-floor fairness, not only mean wait;
4. the learned/CAPR result is compared to at least three baselines on every traffic regime;
5. the public UI can replay a saved experiment and inspect why a call was assigned/reassigned;
6. CI reproduces a deterministic smoke benchmark;
7. README links to a working live demo and committed experiment evidence.

## 6. Non-goals

- safety-critical elevator controller software;
- reverse engineering a real vendor's proprietary controller;
- claiming formal ISO/CIBSE certification;
- pretending synthetic traffic is measured building telemetry;
- declaring algorithmic novelty without a proper literature review.

