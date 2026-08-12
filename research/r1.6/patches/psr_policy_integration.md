# R1.6 PSR Rollout Production Policy Integration

Date: 2026-08-12 (Asia/Bangkok)

## Change

A single scalar `psr_policy_scale` is added to the neural System-2 workspace. It maps to a bounded external policy weight as:

```python
alpha = 2.0 * tanh(psr_policy_scale)
policy_adjustment = alpha * predictive_state_rollout_scores
```

The raw scale initializes at **0**, so legacy/new models preserve the previous action argmax until a calibrated scale is explicitly installed.

Production `forward()` behavior:

- only `policy_mode="full"` may use PSR rollout;
- structured public observation must be present;
- scale=0 skips rollout entirely, avoiding baseline compute overhead;
- active scale uses fixed retained rollout protocol `horizon=2`, `discount=0.7`;
- `semantic_only` remains a clean ablation and is unaffected.

The integration adds **1 trainable parameter**.

## Verification

TDD verifies:

- zero scale produces exactly zero adjustment;
- a raw scale corresponding to alpha `1.2104157209` reproduces `alpha * scores` numerically;
- full forward logits change when PSR scale is activated;
- semantic-only logits remain unchanged by PSR scale.

Full focused R1.6 suite:

```text
47 passed in 16.40s
```

## Parameter accounting

- live System-2 experimental parameters: **21,465,236**
- effective candidate accounting remains below the hard **75M** research ceiling.

## Source hashes

- `cogcoder/neural_system2.py`: `869469bb50d8636ffa681efb905f136bc95e11941af6c80e4c323e544dd2c7f1`
- `tests/test_neural_system2.py`: `15192fcf83ad04b4a7fa788780733513d42a2173f418ebeae723a3bf5b0c5ef2`

Next step: create a locked checkpoint from retained `PredictiveState` weights with the train-only calibrated alpha, verify production forward exactly reproduces the external PSR gate, then evaluate once on another untouched dev slice.

Fresh remains unopened.
