# R1.7 causal-law policy residual — internal rejection

Date: 2026-08-12
Benchmark: FIGG-17 v1.1

The train-only policy calibration did not satisfy the preregistered causal gate, so no policy checkpoint was created and no FIGG-17 dev policy evaluation was opened.

Internal validation (180 rows):
- parent accuracy: 25.56%; CE 5.3678
- epoch-30 accuracy: 26.11%; CE 5.3162
- causal_laws: 33.33% -> 33.33%
- causal_switch: 40.00% -> 40.00%
- goal_inference: 28.57% -> 30.95%
- composition_holdout: 2.08% -> 2.08%

The candidate reduced cross-entropy but failed the required strict improvement in combined causal action accuracy. This branch is therefore rejected.

Interpretation: the accepted law-world model can predict successor dynamics, but the simple policy head does not explicitly relate a predicted effect to the current-versus-desired state difference. This motivates the Goal-Difference Workspace from the already approved R1.7 design rather than further tuning this rejected head.

Policy parameters tested: 263,170. Preregistered protocol commit: `610c2f434e6441609b576f07fee29b4a300e7c9a`.
