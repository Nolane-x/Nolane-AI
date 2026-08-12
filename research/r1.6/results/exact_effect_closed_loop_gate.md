# R1.6 Exact Public Effect -> PSR — Closed-Loop Gate

Date: 2026-08-12 (Asia/Bangkok)

## Gate

Untouched slice: **dev indices 36-41/family**, 18 interactive worlds.

Control and candidate used the same current source. The control loaded retained `PSRPlanner` with the newly introduced `psr_effect_projection` missing from its checkpoint, which loader initializes to exact zeros. The candidate loaded the train-only selected `ExactEffectPSR` projection.

| Checkpoint | Total | Causal | Resource | Rule | Mean steps |
|---|---:|---:|---:|---:|---:|
| PSRPlanner, exact-effect projection = 0 | **3/18** | 0/6 | 3/6 | 0/6 | 7.1111 |
| ExactEffectPSR | **3/18** | 0/6 | 3/6 | 0/6 | 7.1111 |

Task-level completion behavior was unchanged on this gate.

## Verdict

**TRAINED EFFECT PROJECTION REJECTED.**

The exact public effect state is truthful and leakage-free, but learning a 32,768-parameter linear highway into the existing PSR action representation did not convert that evidence into additional closed-loop solutions. `Nolane-R1.6-NS2-PSRPlanner.pt` remains the strongest retained policy checkpoint.

Rejected checkpoint provenance:

- `Nolane-R1.6-NS2-ExactEffectPSR.pt`
- SHA-256: `ae895e39276fe5210c35dfcf39b8f4a180147fb9048b740d4eddcecf5816f33b`
- effective live architecture accounting: `71,026,681`

## Research implication

For opaque deterministic actions, the observed public effect sketch is already a causal model hypothesis. The next experiment should avoid relearning it through another projection and instead test a non-parametric empirical successor prior (`current public predictive state + observed action effect`) with evidence/confidence gating. PSR can then model only residual/state-dependent dynamics.

Fresh remains unopened.
