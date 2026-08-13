# R2.0d Evidence-Conditioned Imagination — Train Gate REJECTED

Date: 2026-08-13
Checkpoint SHA-256: `4dac4bfffa8c007a83d61233100b17fb3214927d9ed76a94a9209f03503f41c9`
Effective parameters: **78,768,917**

## Locked gate (980..999 per family)
- fixed_depth_1: **17/80 = 21.25%**
- fixed_depth_2: **13/80 = 16.25%**
- adaptive: **15/80 = 18.75%**
- fixed_depth_8: **0/80 = 0.00%**
- greedy_parent: **1/80 = 1.25%**
- random: **1/80 = 1.25%**

Primary recursive mode `fixed_depth_2` regressed **5.00 percentage points aggregate** relative to the locked shallow baseline. It also regressed 10 points on `regime_switch` and 10 points on `causal_prerequisites`, violating the family-regression constraint.

## Causal finding
Evidence conditioning was not useless: shallow depth-1 solved **2/20 (10%)** causal-prerequisite tasks whereas R2.0a/b/c solved 0/20 in that family. However, depth-2 remained 0/20 and depth-8 remained 0/20. The evidence-aware world model therefore carries some useful prerequisite information, but the executive cannot reliably use deeper imagined effects for action ranking.

## Decision
**REJECTED.** DEV and FRESH remain unopened. This checkpoint is frozen and will not be tuned after gate exposure.

## Next hypothesis
The shared action scorer currently sees only compact memory metadata. It does not directly receive the actual per-action evidence-effect vector, nor per-action information-gain/failure history. The next candidate will expose those public learned consequences to the action scorer with a small shared projection while preserving the <79M ceiling.
