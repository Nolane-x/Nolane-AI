# R1.8 Reliability Certificate v1 — Rejected

Date: 2026-08-13
Checkpoint: ConditionalLaw `400fc43ef46c9b6c7664703b49c0de7896b49eb728939423288b74847cb27c16`
Calibration: FIGG-18 train indices 32..47/family, 2,753 legal action-state rows.

Preregistered v1 score:
`seen * consistency * context_similarity * exp(-32 * model_memory_mse)`.
Required: >=95% safe-prediction precision overall and in every family for one threshold in {0.5,0.6,0.7,0.8,0.9}. Safe means conditional-law effect MSE <=0.005.

**Verdict: REJECTED.** No threshold passed. No FIGG-18 dev/fresh task was opened.

Diagnostics on the already-consumed train calibration rows (diagnostic only, not a new selection sweep):
- threshold 0.5: coverage 71.85%, overall precision 88.47%; family precision prerequisites 91.81%, conditional 89.38%, implicit-goal 86.49%, regime-switch 78.90%.
- threshold 0.7: coverage 61.75%, overall precision 88.12%; family precision 91.59%, 88.64%, 84.66%, 78.05%.
- threshold 0.9: coverage 22.38%, overall precision 87.18%; conditional-regimes precision falls to 58.62%.

The failure is structural: agreement with the last observed effect is not a monotone proxy for prediction correctness when effects are state-conditional. Increasing the threshold therefore cannot fix calibration reliably.

Next experiment must not reuse indices 32..47 for threshold selection. R1.8 v2 will train only the already-existing 257-parameter `conditional_law_confidence_head` against actual train-only prediction-error labels while freezing the effect model and all parent weights.
