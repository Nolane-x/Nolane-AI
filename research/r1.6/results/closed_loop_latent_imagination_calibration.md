# R1.6 Closed-Loop Latent Imagination — Calibration Result

Date: 2026-08-12 (Asia/Bangkok)

## Protocol

The parameter-free `latent_model_predictive_scores` feature was calibrated only on a small dev-calibration slice: **3 tasks/family = 9 tasks**. A separate validation slice was reserved and was not used because no tested configuration beat calibration baseline. Fresh remained unopened.

The method used the stable `CounterfactualWorld` parent and added `alpha * MPC_score` only in a diagnostic evaluator; production action logits were not modified.

## Observed calibration results

| Horizon | Discount | Alpha | Solved | Notes |
|---:|---:|---:|---:|---|
| 1 | 0.75 | 0.0 | **1/9** | baseline; rule 1/3 |
| 2 | 0.5 | 0.25 | **0/9** | worse |
| 2 | 0.5 | 0.5 | **1/9** | tie; causal 1/3 instead of rule |
| 2 | 0.5 | 1.0 | **1/9** | tie; resource 1/3 instead of rule |

Episode lengths increased substantially under MPC (roughly 8.7-10.3 mean steps vs baseline ~5.8), indicating compounding transition/utility error.

A wider sweep timed out, but because none of the completed configurations exceeded baseline, the protocol intentionally stopped rather than hyperparameter-mining dev.

## Verdict

**Do not integrate MPC scores into the production policy yet.** The architecture test proves that imagined state is action-conditioned, but the learned transition model does not currently provide reliable multi-step value improvement.

Next experiment: directly measure one-step `next_latent_head` accuracy on held-out dev teacher transitions, then improve world-state representation/transition learning before attempting multi-step planning again.
