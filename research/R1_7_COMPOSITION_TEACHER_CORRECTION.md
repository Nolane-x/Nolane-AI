# R1.7 composition teacher correction / evidence invalidation

Date: 2026-08-13

A teacher-trajectory bug was discovered before Latent Program optimization. For `composition_holdout`, `oracle_plan()` returns the full exact hidden functional program from the initial task. The generic collector incorrectly called `oracle_plan()` again after each operation and selected element zero each time. This produced trajectories such as `op1, op1, op1, ...` instead of `op1, op2, submit`.

The collector is now fixed to snapshot the exact initial oracle plan once and replay it sequentially. Regression verifies all 8 train templates produce exactly three labels matching the initial oracle plan.

## Evidence affected

Any earlier **composition action-label diagnostic** that used the old generic collector is not valid evidence for true program induction. In particular, the previously observed ~93.75% standalone composition action-label probe on frozen Goal-Difference relational features must be treated as invalidated because its labels reflected repeated-first-operation trajectories.

Some previously rejected policy-calibration experiments also included composition as a preservation family; those experiments were rejected regardless and no accepted checkpoint depended on their composition preservation score.

## Evidence not affected

- accepted Causal Law world model: trained/evaluated only causal families;
- accepted Goal-Difference progress world model: trained/evaluated only causal families;
- R1.6 EffectProgress fresh-best parent;
- FIGG causal-law / causal-switch world-model evidence.

No FIGG-17 dev/fresh task was opened as a result of this correction.
