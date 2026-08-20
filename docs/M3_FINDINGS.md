# M3 statistical evidence — first 30-seed matrix

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
- Energy is a unitless comparative proxy based on vertical distance + motor starts + service arrivals;
  it is not measured kWh.

The original evidence artifact was produced by GitHub Actions run `32352749591` from head
`6bf62f29e1c8d9628fc6fb0f92ec2a561570cde5`. The checked-in regression baseline stores the
trace-manifest digest and headline metrics so later code changes cannot silently move the result.

## CAPR versus collective

| Scenario | Collective avg wait | CAPR avg wait | Delta | Paired dz | Collective P95 | CAPR P95 | Energy: collective → CAPR | Guardrail result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Morning | 13.34 s | 16.05 s | +2.71 s | +0.72 | 23.71 s | 29.68 s | 599 → 811 | no mean improvement |
| Lunch | 24.15 s | 22.16 s | -1.99 s | -0.30 | 62.27 s | 62.92 s | 1650 → 1660 | candidate improvement |
| Normal | 16.18 s | 12.04 s | -4.14 s | -0.41 | 42.52 s | 26.81 s | 424 → 1122 | mean improves, energy tradeoff |
| Evening | 18.31 s | 19.48 s | +1.17 s | +0.28 | 47.51 s | 49.54 s | 1660 → 1982 | no mean improvement |
| Shock | 21.65 s | 21.75 s | +0.10 s | +0.03 | 60.93 s | 56.72 s | 1703 → 1961 | no mean improvement |
| Mixed day | 50.26 s | 14.66 s | -35.60 s | -1.84 | 129.05 s | 34.85 s | 858 → 1734 | mean improves, energy tradeoff |

Negative delta/dz means lower wait than collective.

## What the evidence supports

CAPR is **traffic-regime dependent**, not globally superior. The cleanest current positive result is
lunch traffic: mean wait falls by about 2 seconds while P95, worst-floor fairness and the configured
energy guardrail remain within tolerance. In normal and mixed-day traffic, CAPR produces much lower
waits but uses far more movement/start/service activity, so those results are deliberately classified
as tradeoffs instead of wins. Morning and evening are negative results for the current CAPR design.

The matrix also shows that a simpler controller can win in some regimes. Nearest-car is the strongest
unconditional candidate in morning traffic in this short-window baseline, while queue-aware is also
a valid lunch candidate. This is useful evidence against overfitting the project narrative to CAPR.

## Important limitation

The 180-second window was chosen so the complete 900-run matrix can be enforced in normal GitHub CI.
It is long enough to expose policy differences and regressions but is not a building traffic-planning
study. M6 must not turn these numbers into real-world performance claims without longer-window,
calibrated demand and sensitivity analysis.
