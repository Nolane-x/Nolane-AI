# R1.6 Effect-to-Progress Critic — reconstructed in authoritative source

Date: 2026-08-12 (Asia/Bangkok)

This record closes the provenance/source divergence discovered after the full R1.6 recovery package was created. GitHub already contained the preregistered `R1_6_EFFECT_PROGRESS_CRITIC_READY.md`, but the recovered local `cogcoder/neural_system2.py` did not yet contain the module. The feature was therefore reconstructed from the GitHub-locked specification using a strict TDD RED→GREEN cycle before any training.

## TDD evidence

RED: three dedicated tests failed because `effect_progress_policy_bonus`, `effect_progress_critic`, and its optimizer scope did not exist.

GREEN: after implementation, the same three tests passed. The complete focused R1.6 suite then passed:

```text
58 passed in 16.54s
```

## Exact architecture contract

`EffectProgressCritic` is a shared relational residual over:

- current public predictive-state sketch: `[B,128]`;
- already-observed action effect sketches: `[B,A,128]`;
- action observation counts: `[B,A]`.

It contains shared bias-free `state_projection: 128→128` and `effect_projection: 128→128`, followed by a shared scorer over

```text
[state, effect, state*effect, abs(state-effect)]
```

with `Linear(512→128) → GELU → LayerNorm(128) → Linear(128→1)`.

A trainable scalar `effect_progress_critic.scale` is initialized to zero. The returned residual is multiplied by `tanh(scale)` and by an observed-evidence mask. Therefore unobserved actions produce **exactly zero** bonus, and old/current-best checkpoints are policy-neutral before training.

The module is action-permutation equivariant by construction: the same transforms/scorer are applied independently to every dynamic action and no action slot ID/name is used.

The full policy path adds this residual only in `policy_mode="full"`, using the same public structured numeric state sketch and contrastive observed effect sketch already used by the accepted PSR line.

Checkpoint loading explicitly permits missing `effect_progress_critic.*` weights so retained pre-feature checkpoints remain loadable.

## Optimizer isolation

`effect_progress_trainable_parameter_names(model)` selects only names beginning with `effect_progress_critic.`. Dedicated test confirms the scope is non-empty and excludes dual-role/parent modules.

## Parameter budget

- new critic parameters: `98,818`
- live R1.6 effective candidate after reconstruction: `71,848,959`
- hard research ceiling: `75,000,000`

## Source integrity

SHA-256 after GREEN gate:

- `cogcoder/neural_system2.py`: `4202f93084325c0018cd3f6da09692b3b865b86a294ba7dc0c2f410c92692aff`
- `cogcoder/neural_system2_training.py`: `0b177551e24e801e79d5aa4f401cd1721912c0b4878d6e8b0180ef838096bf88`
- `tests/test_neural_system2.py`: `3154a10967804a1fb0f716c29f2f1108f9c3ffb673b1f34df1fa2d7ff52fbaa8`
- `tests/test_neural_system2_training.py`: `987e6591c7458fa0f0adefb5434eb068699b8be8fdd40f0303096f2c00ae7c64`

No dev/fresh task was used to reconstruct or verify the feature. Next step is the preregistered train-only residual experiment on a new procedural slice.