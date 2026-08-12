# R1.6 Causal Failure Diagnostic — Identity Learned, Repetition/Stopping Missing

Date: 2026-08-12 (Asia/Bangkok)

## Evidence source

Task-level traces from the rejected `CausalEvidenceBinder` closed-loop gate (dev48-53/family) were compared with the same-source `PSRPlanner` control. Private action kinds/targets were inspected **only by the benchmark developer for post-hoc diagnosis**; they are not available to the agent and must not enter training/policy inputs.

## Observed behavior

The binder shortened causal episodes dramatically (mean 13.17 -> 8.50 steps) but still solved 0/6. Its characteristic pattern became:

1. probe the three opaque actuators;
2. select one actuator repeatedly 3-5 times;
3. submit;
4. fail.

Examples:

- seed 224673: `M -> K -> Q -> K -> K -> M -> submit`
- seed 224770: `M -> K -> Q -> Q -> Q -> Q -> M -> M -> M -> M -> submit`
- seed 224867: `M -> K -> Q -> K -> K -> K -> M -> submit`

The public goals for these worlds vary substantially, e.g. `(0,2,0)`, `(0,1,0)`, `(1,0,2)`, `(3,1,3)`. Therefore a fixed post-probe repetition pattern cannot solve them.

## Interpretation

The effect-conditioned binder appears to learn **which opaque action is causally relevant**, but its single attended evidence vector is insufficient to robustly represent the relational question:

> for the field this action affects, what is the current value and what is the corresponding desired value?

This is a state-conditioned repetition/stopping problem, not primarily an actuator-identity problem anymore.

## Next architecture

Replace the rejected single-evidence binder with a **dual-role causal binder**:

- one observed effect query per action;
- two learned role-conditioned attention queries over current structured atoms;
- two distinct evidence slots that can discover complementary roles such as current-value vs desired-value without hardcoding JSON keys;
- relational scorer over effect + both evidence slots + their difference/product;
- zero-initialized global scale to preserve the retained parent before training;
- dynamic-action evidence gate and permutation equivariance retained.

The module must be trained on a new train-only slice and pass a new untouched interactive dev gate. Fresh remains unopened.
