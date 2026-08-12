# R1.6 Contrastive Public Causal Effect

Date: 2026-08-12 (Asia/Bangkok)

## Why raw effect memory was insufficient

Direct inspection of opaque causal tasks showed that a public structured delta contains both:

- action-specific state change; and
- background dynamics common to every action, especially `step` and `budget_remaining`.

On a representative causal world, raw actuator sketches had 7-8 nonzero buckets. A coordinate-wise common effect was much smaller in norm but shared across probes; subtracting it left one dominant action-specific signature (~0.91-1.0 magnitude) for each actuator.

## Contrastive effect operator

New parameter-free function:

```python
contrastive_action_effect_sketch(action_effect_sketch, action_counts)
```

Rules:

- untried actions remain exact zero;
- with exactly one observed action, preserve the raw effect verbatim (one-shot evidence must not disappear before background dynamics are identifiable);
- with two or more observed actions, estimate common background dynamics as the mean observed effect and subtract it from every observed action;
- operation is dynamic-action permutation equivariant.

Production PSR rollout now receives this contrastive effect rather than the raw effect sketch.

## TDD evidence

RED: helper did not exist.

GREEN tests verify:

- exactly shared drift is removed from all observed actions;
- unique action signatures survive;
- untried actions remain zero;
- one-shot evidence is preserved;
- output permutes exactly with action order.

Full focused R1.6 gate:

```text
51 passed in 15.91s
```

## Parameter accounting

This patch adds **0 trainable parameters**. The live experimental model still has 21,498,004 System-2 parameters; the previously introduced 32,768-param `psr_effect_projection` remains zero-initialized in the retained PSRPlanner control until a new contrastive-effect training run proves value.

## Source integrity

- `cogcoder/neural_system2.py`: `80d0d9864aa161da4b719f3212574fd8718fe96b5ac8ce6abceb3f43f55584b9`
- `tests/test_neural_system2.py`: `50f94e0f2f002688451b1f9ec4e6ee1df46a3272e7e28c79155beb494b9603cd`

Next gate: train only `psr_effect_projection` on a new train-only slice using contrastive effects, then compare against the same-source zero projection on a new untouched dev slice. Fresh remains unopened.
