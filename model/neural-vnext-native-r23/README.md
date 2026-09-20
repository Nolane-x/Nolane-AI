# Neural vNext Native R23 — conformal action consensus

Status: **PRE-DEVELOPMENT LOCKED; FRESH UNOPENED**.

R23 keeps the learned hidden-goal ensemble but changes the promotion question. The model does not need to identify the exact hidden goal when every goal in its conformal prediction set implies the same causal action.

Train-only calibration therefore measures **override action precision**, not exact goal precision.

At inference:

1. exact public consistency defines the hard goal support;
2. the neural ensemble defines a conformal-style subset inside that support;
3. R23 computes the accepted R11 causal action separately for every goal in that subset;
4. it may override only when all those goals imply the same action and the train-only action guard was accepted;
5. otherwise behavior is exactly accepted R11.

Private goal labels and true-goal teacher actions are used only on train identities for training/calibration. They are unavailable at dev/fresh/inference.

Locked identities:

- train: `6400..6655`
- conformal fit: `6656..6719`
- train-only action-guard validation: `6720..6783`
- primary dev: `1312..1343`
- confirmation: `1344..1375`
- fresh: `280..319` — **UNOPENED**

The train-only action guard requires at least 12 candidate overrides and at least 90% precision versus the true-goal causal teacher action.

Strict promotion still requires total solved gain, implicit-goal solved gain, and exact visible-target family solved counts.
