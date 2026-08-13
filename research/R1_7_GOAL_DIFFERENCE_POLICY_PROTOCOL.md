# R1.7 Goal-Difference policy-calibration protocol

Date: 2026-08-13
Parent candidate: `Nolane-R1.7-NCPM-GoalDifference.pt` (`84c00198b9cc0d65e68789b445c3635dba8403e105b4fc9d05029e047ef3a11a`)
Benchmark: FIGG-17 v1.1

The Goal-Difference progress model has passed its train-internal counterfactual-progress gate with policy scale exactly zero. This stage tests the smallest possible bridge from learned progress knowledge to action selection: train **only** the scalar `goal_difference_policy_scale` while every other parameter remains frozen.

## Isolation

- FIGG-17 `train` only.
- fit indices: `80..91` per family.
- internal-validation indices: `92..95` per family.
- families: `causal_laws`, `causal_switch`, `goal_inference`, `composition_holdout`.
- seed: `170417`.
- exploration prefix: six reachability-safe non-submit actions for interactive families; composition follows the exact functional teacher.
- maximum steps: 14.
- no FIGG-17 dev/fresh task may be instantiated during calibration.

These ranges do not overlap Phase-A policy calibration (`32..47`) or Goal-Difference world-progress training (`56..79` for causal families).

## Model input and residual

For each cached teacher-forced decision state, the frozen parent produces base logits. The frozen Goal-Difference model produces `predicted_progress` from public structured atoms, dynamic actions and accepted Causal Law state. Calibrated logits are:

`base_logits + tanh(goal_difference_policy_scale) * predicted_progress`.

No world-model or representation parameter may receive gradient.

## Optimizer scope

Exactly one parameter:
- `goal_difference_policy_scale`

## Internal gate

The calibrated scalar may proceed to a held-out FIGG-17 dev gate only if:
1. validation cross-entropy is strictly lower than scale-zero parent;
2. overall teacher-action accuracy is no lower;
3. mean `causal_laws` + `causal_switch` accuracy is strictly higher;
4. mean `goal_inference` + `composition_holdout` preservation accuracy is no lower.

Teacher-forced improvement is authorization only, not a capability claim. A separate preregistered closed-loop dev gate is mandatory. FIGG-17 fresh remains unopened.
