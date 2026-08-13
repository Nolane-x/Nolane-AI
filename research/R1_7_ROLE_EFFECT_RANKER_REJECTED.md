# R1.7 Role-Effect Ranker — REJECTED

Date: 2026-08-13
Benchmark: FIGG-17 v1.1 train-only
Protocol: fit 194..209/family; internal validation 210..217/family; 60 epochs; seed 170717.

The ranker optimized tied-best action probability in a key-name-invariant role-relative effect space. Frozen Goal-Difference was the exact-row ranking baseline.

Validation baseline:
- overall ranking: `0.6666666666666666`
- causal_laws: `0.5405405405405406`
- causal_switch: `0.8`

Observed learned pattern:
- aggregate often `0.6736–0.6806`
- causal_switch improved to `0.9`
- causal_laws degraded to approximately `0.459–0.473`

Because the preregistered gate forbids degrading either causal family, no epoch passed. `best_epoch=0`, no candidate checkpoint was created, and FIGG dev/fresh remained unopened.

Interpretation: role-relative effect representation is useful for the public-context switch family, but conditional causal laws require state-conditioned hypothesis/rule induction rather than another shared action scorer. Further scorer capacity would be benchmark farming. R1.7 now moves to the planned Latent Program Inducer, while conditional-law induction remains an explicit unresolved bottleneck.
