# R1.7 Phase B Goal-Difference counterfactual-progress protocol

Date: 2026-08-12
Parent: accepted Causal Law checkpoint `e6c99e5944b68c2fde7f89e7dec478b54e93f3a3250adfd806e1020b46239dbc`
Benchmark: FIGG-17 v1.1

## Purpose

Train the neutral Goal-Difference Workspace to estimate whether a Causal Law model's predicted public successor effect moves the current world toward or away from the desired world. This stage is a progress/world-evaluation gate, not a policy gate.

## Isolation

Only FIGG-17 `train` tasks are permitted.

Families:
- `causal_laws`
- `causal_switch`

Fit indices: `56..71` inclusive per family (32 worlds total).
Internal-validation indices: `72..79` inclusive per family (16 worlds total).
Seed: `170317`.
Exploration prefix: six least-used safe non-submit actions where possible, then exact teacher continuation.
Maximum collected steps: 14.

No FIGG-17 dev or fresh task may enter the collector/trainer.

## Neural inputs

All neural inputs are public-derived:
- frozen structured atom embeddings from the public observation;
- frozen dynamic action embeddings;
- accepted Causal Law recurrent state created only from observed public transitions;
- Causal Law predicted structured successor delta and confidence for each dynamic action.

No simulator-private state or target program is a neural input.

## Targets

For each decision state, clone the **train** simulator and execute every legal non-submit action. The resulting public verifier `progress_delta` is the counterfactual target for that action.

The preregistered baseline is per-action last-observed progress persistence:
- unseen action: predicted progress = 0;
- observed action: reuse the most recent public `progress_delta` produced by that same action.

## Optimizer scope

Train only `goal_difference_*` parameters required for current/target role attention, goal/effect/action relational encoding, and progress scoring.

`goal_difference_policy_scale` stays exactly zero. All R1.6 parent, Causal Law world-model parameters, PSR, EffectProgress, and other policy modules remain frozen.

## Internal acceptance gate

The progress model may proceed to policy calibration only if:
1. aggregate validation progress MSE is strictly lower than the last-progress baseline;
2. `causal_laws` validation MSE is no worse than its baseline;
3. `causal_switch` validation MSE is no worse than its baseline;
4. the checkpoint remains below the 96M parameter ceiling and binds the exact accepted CausalLaws/R1.6 lineage;
5. `goal_difference_policy_scale` remains zero in the saved checkpoint.

A pass is evidence for counterfactual goal-progress modeling only. Closed-loop capability requires a separate train-only policy calibration followed by a preregistered held-out dev gate. FIGG-17 fresh remains unopened.
