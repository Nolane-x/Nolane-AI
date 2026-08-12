# R1.6 Effect-to-Progress Critic — ready for train-only evaluation

Date: 2026-08-12

## Bottleneck addressed

Causal traces show that after probing opaque actions the agent can often identify which actuator is relevant, yet still repeats it the wrong number of times or stops at the wrong state. The missing quantity is not action identity alone but state-conditioned utility of repeating an already-observed effect.

## Module

A small shared `EffectProgressCritic` now scores every dynamic action from:

- the current 128D public structured-state sketch; and
- that action's already-observed 128D causal effect memory.

The scorer is relational: projected state, projected effect, elementwise interaction, and absolute difference feed one shared residual head. Unobserved actions receive an exact zero bonus. A scalar scale is initialized at zero, so legacy/current-best checkpoints are behavior-neutral before training.

## Safety / generalization invariants

- zero causal evidence => exactly zero bonus;
- action permutation => identical permutation of critic scores;
- no fixed action slots or benchmark-specific action names;
- parent policy/world-model/trunk are outside the optimizer scope;
- the dedicated optimizer-scope helper selects only `effect_progress_critic.*` parameters.

The targeted critic, training-scope, model, checkpoint-loader, and neural-System-2 training tests completed successfully before this file was pushed.

The next step is train-only residual learning on a new procedural slice, followed by an internal gate before any new dev slice is opened.
