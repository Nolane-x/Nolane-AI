# R1.7 Goal-Conditioned Advantage policy protocol

Date: 2026-08-13
Parent world model: `Nolane-R1.7-NCPM-GoalDifference.pt` (`84c00198b9cc0d65e68789b445c3635dba8403e105b4fc9d05029e047ef3a11a`)
Benchmark: FIGG-17 v1.1

The one-scalar policy bridge was rejected. This experiment exposes the frozen 384D relational feature immediately before Goal-Difference progress compression and trains a shared action-wise residual head over that feature.

## Architecture

- new module: `goal_difference_advantage_head: Linear(384, 1)`
- weight and bias initialize exactly zero
- no extra policy scale
- bonus is gated by accepted Causal Law confidence
- shared head preserves action-permutation equivariance
- new parameters: 385
- effective architecture: 74,661,382 parameters (<96M)

## Isolation

- FIGG-17 `train` only
- fit indices: `96..107` per family
- internal validation: `108..111` per family
- families: `causal_laws`, `causal_switch`, `goal_inference`, `composition_holdout`
- seed: `170517`
- exploration prefix: six reachability-safe non-submit actions for interactive families; exact functional teacher for composition
- maximum steps: 14
- no FIGG-17 dev/fresh task may be instantiated during optimization or selection

These ranges are new relative to Phase-A policy (`32..47`), Goal-Difference progress (`56..79`) and scalar policy (`80..95`).

## Optimizer scope

Exactly:
- `goal_difference_advantage_head.weight`
- `goal_difference_advantage_head.bias`

All parent, Causal Law, Goal-Difference progress and scalar parameters remain frozen. Configuration is fixed before metrics:
- AdamW
- learning rate: `0.005`
- weight decay: `0.0001`
- 60 epochs
- gradient norm clip: 1.0

## Internal gate

Candidate may proceed to held-out FIGG-17 dev only if:
1. validation cross-entropy is strictly lower than zero-head parent;
2. overall validation teacher-action accuracy is no lower;
3. mean `causal_laws` + `causal_switch` accuracy is strictly higher;
4. mean `goal_inference` + `composition_holdout` preservation accuracy is no lower.

Passing this gate is not a capability claim. Closed-loop dev is mandatory and FIGG-17 fresh remains unopened.
