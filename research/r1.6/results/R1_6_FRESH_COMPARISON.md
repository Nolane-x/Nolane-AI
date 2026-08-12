# R1.6 locked fresh comparison

Benchmark: `nolane-frontier-interactive-v2`, fresh indices 0–19 per family (60 tasks total). All three checkpoints, evaluator code, source hashes, and seeds were locked before fresh evaluation in commit `52e31beb9a569051165d17a7d6eebbee4aac1e12`. No model/source tuning occurred after fresh was opened.

## Results

- PSRPlanner `594e19fa...`: **15/60** — causal 0/20, resource 10/20, rule 5/20.
- EffectProgress `0a168806...`: **28/60** — causal 2/20, resource 20/20, rule 6/20.
- Pre-fresh CurrentBest / RuleProgramBroad `f3108d2e...`: **23/60** — causal 1/20, resource 20/20, rule 2/20.

Oracle solves 60/60. A deterministic 10-repeat random control averages 1.8/60 (3%).

## Paired attribution

EffectProgress versus PSRPlanner: **13 gained, 0 lost**. Gains: causal +2, resource +10, rule +1.

RuleProgramBroad versus EffectProgress: **1 gained, 6 lost**. It loses 1 causal task and 5 rule tasks while resource remains 20/20.

## Verdict

EffectProgress produced a clean fresh generalization gain. The RuleProgramBroad dev improvement did **not** replicate on fresh and is treated as dev overfitting. R1.6 is not retuned after this result; any follow-up must be a new research line with a new evaluation protocol/split.

Local machine-readable comparison SHA-256: `3c157197b9b75f966bfc9af28d13b477481847fadcb0d5a184810e68f995b088`.