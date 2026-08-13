# R1.7 linear Goal-Conditioned Advantage Head — REJECTED

Date: 2026-08-13
Benchmark: FIGG-17 v1.1 train-only calibration
Parent world model: `Nolane-R1.7-NCPM-GoalDifference.pt`

Protocol used new train-only ranges 96..107 fit / 108..111 validation across all four FIGG-17 families. Only the zero-initialized `Linear(384,1)` advantage head (385 parameters) was trainable.

## Result

- accepted for dev: **false**
- base CE: `5.40594482421875`
- lowest observed CE after 60 epochs: `5.399367332458496`
- base overall accuracy: `0.25274725274725274`
- validation overall accuracy after training: unchanged `0.25274725274725274`
- causal_laws: unchanged `0.32558139534883723`
- causal_switch: unchanged `0.3125`
- goal_inference: unchanged `0.32558139534883723`
- composition_holdout: unchanged `0.0625`
- no candidate checkpoint was created
- FIGG-17 dev/fresh remained unopened

The richer pre-progress representation slightly improves likelihood under a linear residual but still cannot change decisions against the frozen base-logit geometry. Next step is diagnostic only: test whether the frozen 384D relational feature has action-label signal under standalone linear and nonlinear probes. Any subsequent candidate must use a new train-only slice.
