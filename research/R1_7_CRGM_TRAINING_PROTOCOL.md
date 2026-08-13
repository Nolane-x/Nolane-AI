# R1.7 Causal Role-Goal Matcher (CRGM) world-model protocol

Date: 2026-08-13
Parent: accepted Goal-Difference checkpoint `84c00198b9cc0d65e68789b445c3635dba8403e105b4fc9d05029e047ef3a11a`
Benchmark: FIGG-17 v1.1

## Purpose

Test whether intervention-derived semantic role binding can convert accepted Causal Law representations into a substantially better causal action-progress model than the learned Goal-Difference attention workspace.

CRGM does not read literal field names. A parameter-free role binder identifies the unique changed multi-position numeric vector after a public intervention and the unique invariant same-shape vector as a target-like role. It emits a 64D key-name-invariant target-current need sketch. A small shared neural matcher scores each action-conditioned retrieved causal law against that need.

## Isolation

- FIGG-17 `train` only.
- families: `causal_laws`, `causal_switch`.
- fit indices: `170..185` inclusive per family (32 worlds total).
- internal validation: `186..193` inclusive per family (16 worlds total).
- seed: `170617`.
- exploration prefix: six reachability-safe non-submit interventions where possible, followed by exact teacher continuation.
- maximum episode steps: 14.
- FIGG-17 dev/fresh remain unopened.

Indices 112..161 were consumed by the role-binding diagnostic and 162..169 by role-binding regression tests; CRGM fitting starts at 170 to avoid designing/training on those diagnostic worlds.

## Neural inputs

Only public-derived quantities:
- parameter-free 64D role-goal need sketch from consecutive public observations;
- role confidence (zero on ambiguity/no evidence);
- accepted Causal Law `retrieved_law` per dynamic action;
- accepted Causal Law confidence per action.

No literal JSON field names, simulator-private target state, hidden actuator identity, or oracle program enters the neural input.

## Targets and baseline

At each role-confident train decision state, the train simulator is cloned and every legal non-submit action is executed to obtain its public `progress_delta` target.

Preregistered baseline: the frozen accepted Goal-Difference model's `predicted_progress` on the same decision state and accepted Causal Law outputs.

Metrics:
1. counterfactual progress MSE;
2. top-action ranking accuracy: predicted best legal non-submit action is correct when its true `progress_delta` is tied for the maximum target progress.

## Optimizer scope

Train exactly CRGM world-model parameters:
- `causal_role_goal_need_projection.*`
- `causal_role_goal_scorer.*`

`causal_role_goal_policy_scale` remains exactly zero. All R1.6, Causal Law and Goal-Difference parameters remain frozen.

Fixed training configuration before metrics:
- AdamW
- learning rate: `0.0005`
- weight decay: `0.0001`
- 40 epochs
- gradient norm clip: 1.0

## Internal acceptance gate

CRGM may proceed to policy calibration only if all are true on indices 186..193:
1. aggregate CRGM MSE is strictly lower than frozen Goal-Difference baseline MSE;
2. aggregate CRGM top-action ranking accuracy is strictly higher than Goal-Difference baseline;
3. `causal_laws` CRGM ranking accuracy is no lower than its baseline;
4. `causal_switch` CRGM ranking accuracy is no lower than its baseline;
5. `causal_role_goal_policy_scale == 0.0` in the saved checkpoint;
6. effective candidate remains below 96M parameters and binds the exact accepted parent lineage.

Passing is evidence for causal role-goal progress modeling only. Closed-loop capability still requires a separate policy calibration and preregistered held-out dev gate. FIGG-17 fresh remains unopened.
