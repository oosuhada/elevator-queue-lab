# M5 model card — dependency-free Dueling Double DQN baseline

## Purpose

M5 asks whether a learned dispatch policy can improve on fixed heuristics without hiding tail,
floor-fairness or energy regressions. The checked-in model is an intentionally small research
baseline, not a production elevator controller and not evidence that reinforcement learning is
universally better than CAPR or collective control.

Artifact: `models/m5-ddqn-baseline.json`

Evidence: `evidence/m5-heldout-evaluation.json`

Reproduce both with:

```bash
python scripts/run_m5_training.py
```

The implementation uses only the Python standard library so the training/evaluation contract is
portable to the same minimal environment as the simulator. It implements a real dueling value /
advantage network and a Double-DQN target: the online network selects the masked next action and
the target network evaluates it.

## MDP contract

### Observation

The state is a fixed **77-value** vector built by `app.learning.build_decision_observation`. The
training environment and deployed `rl` policy call the same function.

- hall call: floor, direction, age, queue size and optional destination;
- current owner: six-car one-hot assignment;
- traffic regime: six-scenario one-hot context;
- per car (L1–L3, H1–H3): availability, floor, direction, load, route size, phase, route-insertion
  pickup ETA, route cost, predicted residual capacity and distance to the regime parking hotspot.

Cars outside the call's bank occupy zero-filled slots. This preserves a stable tensor shape without
making an impossible cross-bank car selectable.

### Action

`Discrete(7)`:

1. L1
2. L2
3. L3
4. H1
5. H2
6. H3
7. HOLD

The action mask closes cross-bank cars and cars whose predicted residual capacity is exhausted.
HOLD is enabled for an existing assignment or when no feasible car exists. External training
actions are applied through the simulator's ordinary assignment/reassignment, route, ledger and
hysteresis invariants rather than through a parallel mock transition model.

### Reward

The scalar reward combines six auditable components. Defaults are checked into
`app.learning.RewardWeights`:

| term | weight | sign / intent |
|---|---:|---|
| mean current waiting age | 0.06 | penalty |
| maximum current waiting age | 0.04 | tail/starvation penalty |
| current floor mean-wait gap | 0.03 | fairness penalty |
| new capacity miss | 2.50 | penalty |
| incremental distance/start/service energy proxy | 0.004 | penalty |
| newly served passenger | 0.30 | reward |

The weights are not claimed to be optimal. Their purpose is to test H4 without optimizing mean
wait alone.

## Training contract

- algorithm seed: **2026**;
- training traffic: morning, lunch, normal, evening, shock;
- training passenger seeds: **1–6**;
- episode length: **120 simulated seconds**;
- epochs: **2** (60 total episodes);
- fixed final checkpoint; held-out results are never used to choose a checkpoint;
- 1,685 optimizer updates in the checked-in run;
- final recorded replay-batch loss: **11.88492099**.

`mixed_day` is excluded from training and is the held-out traffic mixture. Evaluation passenger
seeds **21–30** are disjoint from training for every scenario.

## Held-out result

Evaluation uses common random numbers: for each scenario/seed, collective, CAPR and RL receive the
same passenger trace. The table reports mean wait across 10 held-out seeds; the guardrail is the
existing M3 classification relative to collective.

| scenario | collective AWT | CAPR AWT | RL AWT | RL vs collective | RL guardrail |
|---|---:|---:|---:|---:|---|
| morning | 14.60 s | 16.98 s | **27.87 s** | +13.27 s | no mean improvement |
| lunch | 24.37 s | 22.86 s | **29.88 s** | +5.52 s | no mean improvement |
| normal | 15.22 s | 11.23 s | **25.72 s** | +10.51 s | no mean improvement |
| evening | 18.35 s | 19.18 s | **30.67 s** | +12.32 s | no mean improvement |
| shock | 22.46 s | 22.27 s | **31.90 s** | +9.44 s | no mean improvement |
| mixed_day | 49.71 s | 13.59 s | **40.20 s** | -9.51 s | candidate improvement |

The learned baseline therefore **fails the M5 general-improvement gate**. It is not valid to claim
that this Dueling Double DQN beats collective or CAPR generally. On five regimes it waits markedly
longer. Only the completely held-out `mixed_day` mixture improves collective while remaining inside
the configured fairness/energy guardrails.

The paired mixed-day mean delta is -9.51 s, but its 95% CI half-width is 20.19 s on only ten held-out
seeds, so even that isolated win should be treated as a hypothesis for follow-up rather than a
strong superiority claim.

## Ablation result

The same held-out contract was rerun with each observation feature group zeroed: ETA, load,
capacity, age and pre-positioning context. No ablation changes the high-level verdict: all five
single-regime cases still fail and `mixed_day` remains the only guardrail-clean candidate.

The direction of the changes is also useful negative evidence. Removing age or capacity features
actually lowers mixed-day AWT (to roughly 37.99 s and 38.62 s respectively), while removing
pre-positioning context worsens it to roughly 41.98 s. That means this small network has **not**
learned a clean monotonic analogue of the hand-designed CAPR terms; feature presence alone should
not be interpreted as causal benefit.

## Limitations and intended use

- This is a small standard-library neural baseline chosen for reproducibility, not a tuned PyTorch
  production stack.
- The network controls dispatch/reassignment selection. Parking behavior uses the same explicit
  scenario-aware hotspot contract as CAPR; pre-positioning ablation removes observation context,
  not the parking action itself.
- Synthetic traffic is not measured building telemetry.
- The 180-second evaluation window is intentionally consistent with M3 regression evidence but is
  short relative to a real office operating day.
- M5 should be treated as a negative/mixed result that motivates M6 theory extraction, reward/state
  redesign and stronger learned-controller experiments rather than checkpoint cherry-picking.
