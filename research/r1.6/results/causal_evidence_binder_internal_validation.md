# R1.6 Effect-Conditioned Structured-Atom Binder — Internal Validation

Date: 2026-08-12 (Asia/Bangkok)

## Protocol

- Parent: `Nolane-R1.6-NS2-PSRPlanner.pt`
- Fit: train indices 56-65/family = **30 worlds**, 194 teacher rows
- Internal validation: train indices 66-68/family = **9 worlds**, 62 rows
- Trainable: **295,938** binder parameters only
- Epochs: **80**
- Fresh: **unopened**

The residual is queried only by a contrastive public effect already observed for that action and cross-attends over current public structured atoms. The retained parent policy/PSR/planner is frozen.

## Internal validation

Parent (zero binder):

- CE: `1.027298`
- accuracy: **51.61%**
- causal identification: **39.13%**
- delayed resource: **67.86%**
- compositional rule: **36.36%**

Best epoch 80:

- CE: **`0.881567`**
- accuracy: **67.74%**
- causal identification: **60.87%**
- delayed resource: **85.71%**
- compositional rule: **36.36%**
- bounded binder scale (`tanh(raw)`): **0.55309**

This is a strong train-internal decision-boundary improvement, especially on causal identification, but it is not called a capability gain until interactive held-out evaluation.

## Locked candidate

- checkpoint: `Nolane-R1.6-NS2-CausalEvidenceBinder.pt`
- SHA-256: `5bb02576ea4909462478bad0fe21e4abe780882730e3e3e60553ca164b10958a`
- effective experimental parameters: **71,322,619**

Next gate: same-source zero-binder `PSRPlanner` control versus this candidate on untouched dev indices 48-53/family. Fresh remains unopened.
