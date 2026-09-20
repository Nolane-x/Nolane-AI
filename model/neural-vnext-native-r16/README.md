# Neural vNext Native R16 — development-rejected public dynamics ensemble

Status: **DEV REJECTED; confirmation and fresh never opened**.

R16 moved learning from direct action residuals to a public transition world model. Three independently initialized set-aware neural dynamics models were trained without private goals or oracle action labels.

## Locked dev result

On `dev:864..895`:

- accepted R11: **120/128**, implicit-goal **28/32**
- `dynamics_guarded`: **120/128**, implicit **28/32**, 1 override
- `dynamics_broad`: **120/128**, implicit **28/32**, 6 overrides
- visible-target family solved counts remained exact.

Train-only calibration selected threshold **0.75** with **981/989 exact transitions = 99.19% precision**.

R16 added **114,477 learned successor parameters**.

The model was behaviorally useful but not promotion-eligible: guarded R16 shortened implicit episode 888 from **26 steps to 11** while preserving its solved result, yet no previously unsolved episode became solved.

## Closure

The strict solved-count gate was not relaxed.

- confirmation `dev:896..927` was never opened;
- `fresh:280..319` was never instantiated and remains untouched;
- no retuning on `dev:864..895`;
- R16 closes without merge.

The negative result motivates a distinct successor: use learned dynamics for multi-step model-based planning on new train/dev identities rather than another one-step policy.
