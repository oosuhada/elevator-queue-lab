# M3 statistical evidence — 30-seed office-demand matrix

This document records the first release-quality common-random-number comparison produced by the
M3 experiment engine. It is a baseline, not a claim that the current CAPR weights are optimal.

## Reproduction contract

- 30 deterministic seeds per scenario.
- 6 scenarios: morning, lunch, normal, evening, shock, mixed_day.
- 5 policies: legacy_sticky, nearest_car, collective, queue_aware, CAPR.
- 900 controller runs total.
- Measurement window: 0 s warm-up, 180 s measured simulation.
- Reference policy for paired deltas/effect sizes: collective.
- Same passenger trace digest is used by every policy for a given scenario/seed.
- Demand contract: 85% lobby-linked, 10% 18F roof-access proxy, 5% same-bank inter-floor.
- Lobby-linked direction changes by regime: morning 97% up, lunch 45% up, normal 35% up,
  evening 3% up and shock 2% up.
- Energy is a unitless comparative proxy based on vertical distance + motor starts + service arrivals;
  it is not measured kWh.

The checked-in regression baseline stores the full demand contract, trace-manifest digest and
headline metrics so later changes cannot silently alter either the passenger mix or controller
result. The 85/10/5 mix is a synthetic workplace prior, not measured building telemetry.

## CAPR versus collective

| Scenario | Collective avg wait | CAPR avg wait | Delta | Paired dz | Collective P95 | CAPR P95 | Energy: collective → CAPR | Guardrail result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Morning | 35.70 s | 24.45 s | -11.25 s | -0.44 | 74.42 s | 53.35 s | 801 → 1005 | mean improves, energy tradeoff |
| Lunch | 24.84 s | 21.77 s | -3.08 s | -0.41 | 67.39 s | 65.12 s | 1615 → 1604 | candidate improvement |
| Normal | 18.12 s | 11.48 s | -6.64 s | -0.69 | 49.59 s | 25.38 s | 524 → 1113 | mean improves, energy tradeoff |
| Evening | 20.23 s | 20.70 s | +0.47 s | +0.14 | 54.94 s | 57.16 s | 1646 → 1950 | no mean improvement |
| Shock | 20.64 s | 21.95 s | +1.31 s | +0.24 | 55.44 s | 58.40 s | 1640 → 1944 | no mean improvement |
| Mixed day | 39.32 s | 15.20 s | -24.13 s | -1.30 | 101.27 s | 40.01 s | 893 → 1711 | mean improves, energy tradeoff |

Negative delta/dz means lower wait than collective.

## What the evidence supports

CAPR is **traffic-regime dependent**, not globally superior. The only clean current M3 result is
lunch traffic: mean wait falls by about 3.1 seconds while the configured P95/fairness/energy
guardrails remain within tolerance. Morning, normal and mixed-day all show substantial wait
reductions, but the additional movement/start/service activity violates the current energy budget,
so they remain tradeoffs. Evening and shock are negative mean-wait results.

The matrix also shows that a simpler controller can win in some regimes. In the highly lobby-centric
morning model, `legacy_sticky` averages 16.67 s and nearest-car 19.37 s, both materially below CAPR
24.45 s and collective 35.70 s. That result is useful evidence against overfitting the narrative to
predictive complexity simply because the controller has more state.

## Important limitation

The 180-second window was chosen so the complete 900-run matrix can be enforced in normal GitHub CI.
It is long enough to expose policy differences and regressions but is not a building traffic-planning
study. M6 must not turn these numbers into real-world performance claims without longer-window,
calibrated demand and sensitivity analysis.
