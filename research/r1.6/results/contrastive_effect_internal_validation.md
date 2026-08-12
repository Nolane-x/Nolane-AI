# R1.6 Contrastive Public Effect -> PSR — Internal Validation

Date: 2026-08-12 (Asia/Bangkok)

## Candidate

- Parent: `Nolane-R1.6-NS2-PSRPlanner.pt`
- Fit: train indices 43-52/family = **30 worlds**, 207 teacher steps
- Internal validation: train indices 53-55/family = **9 worlds**, 64 teacher steps
- Trainable parameters: **32,768** (`psr_effect_projection.weight` only)
- Retained epochs: **40**
- Fresh: **unopened**

A prior 100-epoch invocation timed out at epoch 20 before any checkpoint was saved and is therefore not treated as a result. The 40-epoch run reused exactly the same data, seed and objective and completed with a checkpoint.

## Internal validation

Initial zero projection:

- loss: `0.1566441`
- state MSE: `0.00318023`
- persistence MSE: `0.00444772`
- failure accuracy: `95.57%`
- done accuracy: `100%`

Best epoch 40:

- loss: **`0.1542313`**
- state MSE: **`0.00317592`**
- persistence MSE: `0.00444772`
- failure accuracy: **`95.94%`**
- done accuracy: **`100%`**

Family state MSE at best epoch:

| Family | Candidate MSE | Persistence MSE |
|---|---:|---:|
| causal identification | 0.0020010 | **0.0018005** |
| delayed resource | **0.0017613** | 0.0043440 |
| compositional rule | **0.0089205** | 0.0102984 |

The predictive-state aggregate qualifies for one new closed-loop gate, but causal successor prediction still does not beat persistence. No capability claim is made from this internal metric.

## Locked candidate

- `Nolane-R1.6-NS2-ContrastiveEffectPSR.pt`
- SHA-256: `f67572dd20665148e946353826f93ccae33f9e30a446b8b661b78d6f41cfa142`
- effective experimental parameter accounting: **71,026,681**

Next gate: same-source zero-projection `PSRPlanner` control versus this candidate on untouched dev indices 42-47/family. Fresh remains unopened.
