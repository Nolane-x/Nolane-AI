# R1.7 Role-Effect Ranker train-only protocol

Date: 2026-08-13
Benchmark: FIGG-17 v1.1
Parent world/law stack: accepted Goal-Difference + Causal Laws. FIGG dev/fresh unopened.

## Motivation

CRGM latent matching was rejected and fixed role-effect Euclidean geometry only tied the Goal-Difference ranking baseline. This experiment learns a tiny shared ranker directly in the aligned role-relative coordinate system and optimizes the metric that prior MSE-first models failed to improve: **best-action ranking**.

## Isolation

- families: `causal_laws`, `causal_switch`
- FIGG `train` only
- fit indices: `194..209` inclusive per family (32 worlds)
- internal validation: `210..217` inclusive per family (16 worlds)
- seed: `170717`
- exploration prefix: six reachability-safe non-submit interventions, followed by exact teacher continuation
- maximum steps: 14

Earlier diagnostic/training ranges end at 193, so these worlds are new to this candidate.

## Inputs

Only public-derived representations:
- 64D target-current need sketch from parameter-free causal role binding;
- accepted Causal Law `predicted_delta`, parameter-free projected into the same 64D role-relative effect coordinates;
- role confidence and Causal Law confidence.

No literal field-name semantics or simulator-private actuator identity enters the ranker.

## Architecture and optimizer

Shared `Linear(256,128) -> GELU -> LayerNorm(128) -> Linear(128,1)` over `[need,effect,need*effect,|need-effect|]`.

- output layer zero-initialized
- parameters: 33,281
- effective live architecture: 74,974,217 (<96M)
- optimizer scope exactly `causal_role_effect_ranker.*`
- AdamW, lr `0.001`, weight decay `0.0001`
- 60 epochs
- gradient clipping 1.0

## Objective

For each role-confident decision state, clone the train simulator and execute every legal non-submit action to obtain true public `progress_delta`. Every action tied for maximum true progress is a valid target. Optimize negative log probability mass on the tied-best action set.

Frozen comparison baseline on the exact same rows: accepted Goal-Difference `predicted_progress` ranking.

## Internal gate

Proceed to policy integration only if:
1. aggregate Role-Effect ranking accuracy is **strictly higher** than Goal-Difference baseline;
2. `causal_laws` ranking is no lower than baseline;
3. `causal_switch` ranking is no lower than baseline;
4. no parent/world-model parameter receives gradient;
5. FIGG dev/fresh remain unopened.

Passing this gate is still not a closed-loop capability claim. A new train-only policy-integration slice and preregistered dev gate are required.
