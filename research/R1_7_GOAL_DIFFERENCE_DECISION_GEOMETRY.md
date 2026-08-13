# R1.7 Goal-Difference decision-geometry diagnostic

Date: 2026-08-13
Source: rejected scalar-policy validation cache (FIGG-17 train indices 92..95). No dev/fresh task was opened.

The one-scalar bridge failed because useful world-model information is compressed into a tiny scalar that neither has sufficient magnitude nor sufficient action-ranking quality.

## Measured geometry (186 teacher-forced decision rows)

- base policy accuracy: `0.20967741935483872`
- `predicted_progress.argmax` teacher accuracy: `0.22580645161290322`
- teacher progress beats the base policy's strongest competing action on only `47.85%` of rows
- mean base-logit teacher deficit versus its strongest competitor: approximately `2.98537`
- mean Goal-Difference progress gap on the same comparison: approximately `2.06e-5`
- median additive scale required on rows where progress points in the helpful direction: approximately `20,820x`

Family progress-argmax accuracy:
- causal_laws: `0.32558`
- causal_switch: `0.33333`
- goal_inference: `0.23404`
- composition_holdout: `0.02083`

## Conclusion

Arbitrarily increasing the global scalar would be an unstable benchmark hack and still cannot fix rows where the progress ranking itself is wrong. The accepted Goal-Difference world model remains useful, but policy needs access to the richer relational representation *before* it is compressed to one progress scalar.

Next experiment: a zero-initialized, shared Goal-Conditioned Advantage Head over frozen Goal-Difference relational features. It must remain action-permutation equivariant and use a new train-only slice. FIGG-17 dev/fresh remains unopened.
