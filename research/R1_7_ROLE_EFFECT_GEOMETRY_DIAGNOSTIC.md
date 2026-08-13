# R1.7 role-projected causal geometry diagnostic

Date: 2026-08-13
Scope: diagnostic only on already-consumed CRGM validation worlds 186..193; no dev/fresh use.

After CRGM latent matching was rejected, accepted Causal Law `predicted_delta` was projected parameter-free from path-specific structured-delta space into the same 64D role-relative position/value coordinates as the target-current need sketch. A fixed geometric score measured reduction in squared need distance:

`score = (||need||^2 - ||need - projected_effect||^2) / (||need||^2 + eps)`

and was gated by Causal Law confidence.

## Result (163 decision rows)

Overall:
- role-effect geometry: `94/163 = 57.6687%`
- frozen Goal-Difference baseline: `94/163 = 57.6687%`

By family:
- causal_laws: geometry `36/83 = 43.3735%`; baseline `35/83 = 42.1687%`
- causal_switch: geometry `58/80 = 72.5%`; baseline `59/80 = 73.75%`

## Conclusion

The role-relative projection is information-preserving enough to match the learned baseline and slightly improves conditional-law ranking, but a fixed Euclidean utility is not a capability gain. It is not promoted as a candidate.

The next experiment trains a very small shared **Role-Effect Ranker** directly on aligned `[need, effect, interaction]` features with an action-ranking objective, using entirely new train-only ranges. This targets the exact metric that prior MSE-oriented models failed to improve.
