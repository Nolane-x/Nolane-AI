# R1.6 Exact Public Effect -> PSR — Train-Internal Validation

Date: 2026-08-12 (Asia/Bangkok)

## Candidate

- Parent: `Nolane-R1.6-NS2-PSRPlanner.pt`
- Fit: train indices 30-39/family = **30 worlds**, 197 teacher steps
- Internal validation: train indices 40-42/family = **9 worlds**, 63 teacher steps
- Trainable parameters: **32,768** (`psr_effect_projection.weight` only)
- Epochs: **100**
- Fresh: **unopened**

The recurrent state carries an exact public 128D effect sketch for each dynamic action. The only learned component maps that public effect sketch into the existing 256D PSR action representation; all retained PSRPlanner weights are frozen.

## Internal validation

Initial (effect projection = zero):

- validation loss: `0.1704157`
- state MSE: `0.00264221`
- persistence MSE: `0.00384477`
- failure accuracy: `94.14%`
- done accuracy: `100%`

Best epoch 100:

- validation loss: **`0.1625971`**
- state MSE: **`0.00261983`**
- persistence MSE: `0.00384477`
- failure accuracy: **`94.87%`**
- done accuracy: **`100%`**

Family state MSE at best epoch:

| Family | Candidate MSE | Persistence MSE |
|---|---:|---:|
| causal identification | 0.0014713 | **0.0013141** |
| delayed resource | **0.0017878** | 0.0040299 |
| compositional rule | **0.0063666** | 0.0069625 |

Causal state prediction is still slightly worse than persistence, so this train-only result is **not** called a capability gain. It merely qualifies the candidate for one new held-out closed-loop dev gate.

## Locked candidate

- checkpoint: `Nolane-R1.6-NS2-ExactEffectPSR.pt`
- SHA-256: `ae895e39276fe5210c35dfcf39b8f4a180147fb9048b740d4eddcecf5816f33b`
- effective candidate parameters: **71,026,681**

Next gate: compare the zero-effect same-source `PSRPlanner` control against this candidate on untouched dev indices 36-41/family, then preserve or reject the 32,768-parameter effect highway based on actual interactive completion and cross-family regression.
