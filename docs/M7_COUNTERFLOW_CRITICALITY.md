# M7 — Counterflow Criticality Hypothesis

## Abstract

The earlier Elevator Queue Lab evidence showed that predictive reassignment is useful in some
traffic regimes and wasteful in others, but a scenario label such as `lunch` or `morning` is not a
theory. M7 asks a narrower causal question: **when does continuously reconsidering an already
assigned hall call become worth doing?**

To isolate that intervention, M7 introduces `capr_static`, an ablation that uses the exact CAPR
initial scoring and parking logic but disables periodic reassessment of calls that already have an
owner. CAPR and CAPR-static therefore differ principally in continuous predictive reassignment.

Across a controlled 40-cell discovery surface (3,600 controller runs), the quantity

\[
M(p)=4p(1-p), \qquad B=\lambda M(p)
\]

emerges as a compact predictor of reassignment value, where `λ` is total passenger arrival
intensity and `p` is the up-direction probability inside the fixed lobby-linked traffic stream.
`M` is zero for one-way traffic and one for a 50/50 stream. Because this experiment fixes the
lobby-linked share at 85%, `B` should be read as a **normalized bidirectional-load index**, not as a
universal physical constant.

In the discovery grid, `B` correlates with the CAPR-minus-static average-wait effect at **r =
-0.748** and with the P95 effect at **r = -0.741**. A simple empirical fit is

\[
\Delta W_{CAPR-static}\;[s] \approx 0.657 - 0.158B,
\]

with discovery `R² = 0.560`. A classification threshold near **B = 12.33** identifies 35 of 40
discovery cells correctly when the target is a paired 95%-CI-supported mean-wait improvement.

The threshold was then frozen and challenged on a separate 18-cell grid containing arrival rates
and direction ratios not used to fit it (1,080 additional controller runs). Held-out accuracy falls
to **13/18 = 72.2%**: all five supported gains are captured (100% recall), but five additional cells
are false positives under the strict confidence-interval criterion. Importantly, every held-out
threshold-positive cell still has a negative point estimate for average-wait change. The continuous
effect model generalizes more smoothly: held-out predicted versus observed effects correlate at
**r = 0.672**, with **0.805 s MAE**.

The evidence therefore supports a **fuzzy phase transition**, not a hard theorem: low bidirectional
load makes continuous reassignment mostly churn; sufficiently high counterflow/load makes it
increasingly valuable, with a transition region where stochastic uncertainty and other state
variables still matter.

![M7 counterflow criticality evidence](assets/m7-counterflow-criticality.svg)

## 1. Why this experiment exists

M3 and M6 support a regime-gated controller rather than a global CAPR winner. The strongest
examples look contradictory if the traffic regime is treated only as a name:

- morning is high volume, yet simple low-churn policies are excellent;
- lunch is less directional and is the cleanest CAPR regime;
- normal and mixed-day traffic can show large wait gains but movement/energy tradeoffs;
- evening and shock do not establish unconditional CAPR superiority.

One plausible explanation is that **arrival volume alone is not the state variable that determines
the value of reassignment**. A nearly one-way queue produces a stable service objective: repeatedly
changing ownership can create churn without resolving much route competition. When meaningful
counterflow exists at the same time as high demand, different hall calls compete for car routes and
an assignment that was good a few seconds ago can become stale.

M7 converts that explanation into a falsifiable experiment.

## 2. The clean ablation: CAPR versus CAPR-static

Comparing CAPR directly with collective control is insufficient for causal interpretation because
their initial assignment scores, parking behavior and reassignment rules all differ. M7 therefore
adds an internal research policy:

`capr_static`

- exact inherited CAPR candidate scoring;
- exact inherited CAPR parking targets;
- same simulator, physics, capacity and failed-pickup behavior;
- **continuous_reassignment = false**.

The full `capr` policy is identical except that owned calls are periodically re-evaluated. The
paired outcome

\[
\Delta W = W_{CAPR}-W_{CAPR-static}
\]

therefore estimates the marginal value of continuous predictive reassignment much more cleanly
than the M3 policy-ranking comparison. Negative `ΔW` is beneficial.

This is still not a perfect causal intervention: later state trajectories diverge after the first
different reassignment. That divergence is the treatment effect we intend to measure, but it means
individual event-level mechanisms require additional mediation experiments before causal language
is extended beyond the controller switch itself.

## 3. Controlled traffic surface

M7 keeps the synthetic workplace purpose mix fixed:

- 85% lobby-linked;
- 10% 18F roof-access proxy;
- 5% same-bank inter-floor.

The discovery surface changes two quantities independently:

| variable | discovery grid |
|---|---|
| total arrival intensity `λ` | 5, 10, 16, 22, 28 passengers/min |
| lobby up probability `p` | 0.03, 0.15, 0.30, 0.45, 0.50, 0.70, 0.85, 0.97 |
| cells | 40 |
| common seeds | 30/cell |
| policies | CAPR-static, CAPR, collective |
| window | 180 s, zero warm-up |
| controller runs | 3,600 |

Every policy in one cell receives the same seeded passenger trace. The simulator runs in one
neutral scenario context so the CAPR/CAPR-static parking implementation is identical across the
controlled surface.

The held-out validation surface is deliberately different:

| variable | held-out grid |
|---|---|
| total arrival intensity `λ` | 13, 19, 25 passengers/min |
| lobby up probability `p` | 0.10, 0.25, 0.40, 0.60, 0.75, 0.90 |
| cells | 18 |
| common seeds | 30/cell |
| policies | CAPR-static, CAPR only |
| controller runs | 1,080 |

The threshold and linear effect model are frozen before this second grid is evaluated.

## 4. Deriving the candidate state variable

Let `p` be the fraction of lobby-linked traffic traveling upward. The simple symmetric mixing term

\[
M(p)=4p(1-p)
\]

has useful properties for this experiment:

1. `M=0` at `p=0` or `p=1`: one-way traffic;
2. `M=1` at `p=0.5`: maximal directional mixing;
3. `M(p)=M(1-p)`: the first-order index does not assume up-flow and down-flow are inherently
   different;
4. multiplying by arrival intensity gives a load-like quantity with a traffic-rate scale.

Define the **normalized bidirectional-load index**

\[
B=\lambda 4p(1-p).
\]

This is not the literal minority-direction arrival rate. Near a one-way regime, if `q` is the small
opposite-direction share, `4p(1-p)≈4q`; near balanced traffic it saturates at one.

Because M7 holds the lobby share at 0.85, the data cannot distinguish `B` from
`0.85B` except for a constant rescaling. A later experiment must vary the lobby share before the
absolute normalization of B can be claimed to have physical meaning.

## 5. Discovery result — three empirical phases

The relationship is monotonic enough to be useful but noisy enough that a hard threshold would
overstate the evidence.

| B range | cells | mean CAPR−static AWT | mean energy ratio | CI-supported gain cells | clean gain cells |
|---|---:|---:|---:|---:|---:|
| 0–4 | 12 | **+0.659 s** | 1.113 | 0 | 0 |
| 4–8 | 6 | **+0.051 s** | 1.055 | 0 | 0 |
| 8–12 | 8 | **−1.080 s** | 1.069 | 2 | 1 |
| 12–16 | 5 | **−2.574 s** | 1.059 | 4 | 4 |
| ≥16 | 9 | **−2.606 s** | 1.035 | 7 | 7 |

This suggests three operational phases.

### Static/churn phase — low B

At very low B, continuous reassignment has no CI-supported wins in this grid. In the 0–4 bin it
actually increases mean wait by about 0.66 s on average while the energy proxy is about 11.3%
higher. Calls are being reconsidered, but there is too little competing directional demand for that
extra flexibility to pay for itself.

### Transition phase — intermediate B

Around B≈8–12, point estimates begin to favor continuous reassignment, but confidence intervals are
often wide. Other state variables—specific route geometry, queue imbalance, current car positions,
capacity occupancy and finite 180 s sampling—can still dominate individual cells.

### Predictive-value phase — high B

Above roughly B≈12 in the discovery surface, most cells show large service gains without tripping
the 10% energy-ratio guard. The B≥16 cells average about 2.61 s lower AWT and seven of nine are
clean, CI-supported gains.

## 6. The strongest counterexample matters as much as the strongest win

The strongest discovery gain occurs at:

- λ = 28 passengers/min;
- p↑ = 0.85;
- B = 14.28;
- ΔAWT = **−5.856 s**;
- ΔP95 = **−27.395 s**;
- energy ratio = **1.078**.

High demand alone does not explain this result. A high-volume, almost pure up-peak cell provides the
opposite counterexample:

- λ = 22 passengers/min;
- p↑ = 0.97;
- B = 2.56;
- ΔAWT = **+3.034 s**;
- ΔP95 = **+8.667 s**;
- energy ratio = **1.259**.

So the rule supported by M7 is not “reassign more under congestion.” It is closer to:

> **Reassignment becomes valuable when congestion contains enough directional competition.**

That distinction explains why a very busy morning up-peak can prefer a stable low-churn policy
while a somewhat less one-way lunch wave can benefit from predictive reassignment.

## 7. Fitted effect law and the fuzzy critical region

The discovery fit is:

\[
\Delta W\;[s] \approx 0.657 - 0.158B,\quad R^2=0.560.
\]

The fitted point-estimate crossover is only B≈4.16, but a stricter question—“when is the paired
mean-wait gain strong enough that its 95% CI is entirely below zero?”—produces a discovery threshold
near **B=12.33**.

On the discovery surface that threshold classifies 35/40 cells correctly:

- true positive: 11;
- false positive: 3;
- true negative: 24;
- false negative: 2.

The difference between the mean crossover and the confidence-supported trigger is intentional.
The former describes expected effect direction; the latter describes when this finite experiment
has enough effect size relative to seed variance to call the gain supported.

## 8. Held-out falsification — the threshold weakens, the continuous relationship survives

The frozen B≈12.33 threshold is tested on 18 unseen combinations of λ and p.

Result:

- accuracy: **72.2% (13/18)**;
- true positives: **5**;
- false positives: **5**;
- true negatives: **8**;
- false negatives: **0**;
- supported-gain recall: **100%**;
- supported-gain precision: **50%**.

All ten held-out cells above the threshold have a negative mean CAPR−static ΔAWT, including the five
that fail the strict CI-support criterion. The binary threshold is therefore better interpreted as
a **high-recall high-effect screening boundary** than a deterministic switch.

The continuous model is more convincing than the hard classifier. Without refitting coefficients,
the discovery equation predicts held-out effect magnitude with:

- observed-vs-predicted correlation: **0.672**;
- mean absolute error: **0.805 s**;
- RMSE: **1.125 s**.

This is the reason the M7 result is called **Counterflow Criticality Hypothesis**, not “Counterflow
Criticality Law.” A phase-like transition appears, but the transition is fuzzy.

## 9. Control consequence — a frozen B-gate keeps most wait benefit with less churn

A useful empirical theory should make a prospective control prediction. Without fitting anything
to the held-out outcomes, take the already-frozen B≈12.33 discovery trigger and apply this simple
selector to the 18 validation cells:

> if B ≥ 12.33, use continuous CAPR; otherwise use CAPR-static.

This is an **offline policy-selection projection** over policies that were already simulated on the
held-out traces, not a claim that a live online estimator has been implemented. It nevertheless
tests the practical implication of the frozen theory.

Across the held-out cells:

- always-on CAPR mean ΔAWT versus static: **−1.390 s**;
- B-gated mean ΔAWT versus static: **−1.225 s**;
- per-cell mean oracle: **−1.429 s**;
- B-gate retains **88.1%** of the always-on CAPR wait gain and **85.7%** of the per-cell mean oracle gain;
- always-on CAPR mean energy ratio versus static: **1.078**;
- B-gated mean energy ratio versus static: **1.033**;
- the gate reduces CAPR's additional energy overhead by **58.3%** while activating continuous
  reassignment in only **10 of 18** held-out traffic cells.

This is the strongest engineering implication of M7 so far: **continuous reassignment may be more
useful as a conditionally enabled intervention than as a permanently active controller feature.**
The next milestone should replace the experiment's known λ/p values with an online estimator and
test the gated controller prospectively on traces never used for discovery or validation.

## 10. Approximate counterflow requirement in up-peak traffic

For an up-dominant lobby stream, write the small counterflow fraction as `q=1-p`. If a future
controller uses B≈12.33 only as a high-effect screening threshold, solving

\[
4\lambda q(1-q)=12.33
\]

gives the following discovery-grid projections:

| λ | approximate critical opposite-direction share |
|---:|---:|
| 16/min | 26.1% |
| 22/min | 16.9% |
| 28/min | 12.6% |

This yields an intuitive prediction: **the busier the building, the smaller the counterflow share
needed before stale assignment correction can become material.** These percentages are derived from
the project-specific fuzzy threshold, not standards guidance and not a field-calibrated constant.

## 11. Relation to the canonical office scenarios

Projecting the original scenario parameters onto B gives a useful consistency check:

| scenario | λ | p↑ | B | M7 region | prior M3 behavior |
|---|---:|---:|---:|---|---|
| morning | 22 | 0.97 | 2.56 | static/churn | simple sticky/nearest are very strong; CAPR spends more energy |
| lunch | 16 | 0.45 | 15.84 | predictive | cleanest CAPR candidate improvement |
| normal | 5 | 0.35 | 4.55 | transition | CAPR has service gain but large movement tradeoff vs collective |
| evening | 22 | 0.03 | 2.56 | static/churn | no unconditional CAPR mean-wait win |

M7 and M3 use different policy contrasts, so this is **consistency evidence**, not a statistical
validation of the M7 threshold. M7 compares CAPR with CAPR-static; M3 compares independently
designed policies. The notable point is that the candidate state variable explains the qualitative
scenario ordering without using the scenario labels themselves.

## 12. What is and is not new here

The project does **not** claim that traffic-pattern awareness, counterflow effects, threshold
dispatch, or elevator phase transitions are new ideas.

- Pepyne & Cassandras (1997) derive threshold-based optimal dispatch structure for up-peak traffic,
  with thresholds depending on arrival rate and system state: <https://doi.org/10.1109/87.641406>.
- Nagatani (2004) studies dynamical transitions in peak elevator traffic as loading, capacity and
  elevator count change: <https://doi.org/10.1016/j.physa.2003.10.001>.
- Older Otis dispatch work explicitly discusses significant counterflow/inter-floor traffic and
  repeated hall-call reassignment: <https://patents.google.com/patent/US5714725A/en>.
- Modern work explicitly treats up-peak, down-peak, lunch-peak and inter-floor patterns as dispatch
  context: <https://www.sciencedirect.com/science/article/pii/S1474034624001459>.

The narrower contribution tested here is the combination of:

1. a controlled CAPR-versus-CAPR-static reassignment ablation;
2. the symmetric load/mixing variable `B=λ4p(1-p)`;
3. an empirical CAPR reassignment effect curve;
4. a separately held-out λ/p grid that attempts to falsify the fitted transition.

Whether that combination constitutes publishable novelty requires a substantially broader
literature review and independent replication. The repository deliberately calls it a **candidate
empirical theory** until then.

## 13. Falsification roadmap

The hypothesis should be rejected or revised if any of these follow-up tests fail:

1. **Vary lobby share.** M7 fixes it at 85%; test whether the physically scaled
   `λ·lobby_share·4p(1-p)` collapses data better than the current normalized B.
2. **Vary car capacity and fleet size.** A true dimensionless law should likely normalize load by
   service capacity; the current B does not.
3. **Vary building height/bank topology.** Repeat on 10/18/30-floor and different zoning layouts.
4. **Extend run duration.** Repeat the phase map at 900 s or full-day windows to reduce finite-window
   effects.
5. **Use measured or independently generated OD traces.** The current result is still synthetic.
6. **Test causal mediators.** Determine whether route conflict, assignment age, capacity risk or
   queue imbalance explains the residual error after B.
7. **Prospectively gate CAPR.** Implement a controller that observes B online and enables continuous
   reassignment only in the predicted phase; compare it to always-on CAPR and CAPR-static on traces
   that were not used to fit the gate.

The last test is the strongest engineering consequence. If a B-gated controller preserves CAPR's
high-B service gains while avoiding low-B churn/energy cost, the hypothesis becomes not only an
explanation but a useful control rule.

## Reproduction

Discovery sweep:

```bash
python scripts/run_m7_theory_sweep.py --seconds 180 --seeds 30
```

Frozen-threshold held-out validation:

```bash
python scripts/run_m7_threshold_validation.py --seconds 180 --seeds 30
```

Figure generation:

```bash
python scripts/generate_m7_assets.py
```

Machine-readable artifacts:

- `evidence/m7-bidirectional-load-sweep.json`
- `evidence/m7-threshold-validation.json`

The public dashboard reads the same committed artifacts through `/api/theory`; it does not recreate
the conclusions from hand-entered numbers.
