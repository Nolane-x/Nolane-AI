# Neural vNext Native R16 — public dynamics ensemble

Status: **DEVELOPMENT LOCKED; fresh unopened**.

R16 is the next learned Neural Core experiment after accepted R11.

Instead of learning a direct action residual (the R12 failure mode), R16 learns the **public transition dynamics** of hidden-goal tasks. Three independently initialized set-aware neural world models observe only public state/action-memory features and predict the next-state delta for each opaque actuator.

A neural prediction may affect control only when:

1. all ensemble members agree on the entire 3-coordinate transition;
2. confidence clears a threshold selected on a disjoint **train-only calibration** range;
3. the public hidden-goal posterior is inside the preregistered support gate;
4. the predicted action is strictly better than accepted R11 by the locked distance margin.

Otherwise R16 returns accepted R11 exactly.

No private goal or oracle action is used to train the world model. Visible-target episodes structurally return R11 unchanged.

Locked ranges:

- world-model train: `train:4096..4351`
- train-only calibration: `train:4352..4479`
- primary dev: `dev:864..895`
- confirmation: `dev:896..927`
- reserved fresh: `fresh:280..319` — **UNOPENED**
