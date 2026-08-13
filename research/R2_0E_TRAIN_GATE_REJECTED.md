# Nolane R2.0e Evidence-Effect Executive — Train Gate Rejected

Date: 2026-08-13

## Decision

**REJECTED for recursive-compute admission.** The candidate substantially improves raw closed-loop action policy over earlier R2.0 candidates, but the preregistered recursive primary (`fixed_depth_2`) does not beat the same executive at `fixed_depth_1`; it is worse in aggregate and regresses two families by 10 percentage points. DEV and FRESH remain unopened.

## Bound candidate

- parent: `Nolane-R1.9-78M-STRONGEST-ONE-WEIGHT-FP16.pt`
- parent SHA-256: `6081a38f65142ae06dc36cba1c9a567a9d0754c08d683d89a8e76f7aade9c52a`
- R2.0e delta: `Nolane-R2.0e-RIE-EvidenceEffect.pt`
- delta SHA-256: `cb56914f3c9be1c2b0f0b77ff8cb14c16fbca5b2e42d16f227410fc335bf0e0e`
- executive parameters: **565,080**
- effective total: **78,779,253**
- best epoch: **25/25** by locked validation total loss
- validation loss: **0.8352651538**
- validation action accuracy: **56.6416%**
- validation depth accuracy: **100%**

## Untouched train gate

Gate block: FIGG-18 `train` indices `1280..1299`, four families, 20 worlds per family, beam width 1.

| Mode | Solved | Solve rate |
|---|---:|---:|
| random | 0/80 | 0.00% |
| greedy parent | 1/80 | 1.25% |
| **fixed depth 1** | **36/80** | **45.00%** |
| **fixed depth 2** | **34/80** | **42.50%** |
| fixed depth 8 | 32/80 | 40.00% |
| adaptive | 34/80 | 42.50% |

The preregistered requirement was at least **+10.0 percentage points** for depth 2 over depth 1, with no family regression worse than 5 points. Observed aggregate gain was **-2.5 points**.

Per-family depth-2 minus depth-1:

- `conditional_regimes`: 65% -> 65% (**0 pp**)
- `regime_switch`: 50% -> 40% (**-10 pp**)
- `implicit_goal_regimes`: 55% -> 65% (**+10 pp**)
- `causal_prerequisites`: 10% -> 0% (**-10 pp**)

Both the aggregate rule and family-regression rule fail.

## What improved anyway

The rejection is specifically about **recursive compute**, not about the evidence-effect executive being useless. The same R2.0e network at shallow depth 1 solves **45%** of the 80 locked worlds, compared with only 1.25% for the frozen parent-impact heuristic and 0% for deterministic random. Earlier R2.0c/d shallow closed-loop rates were around the high teens/low twenties. Direct observed action-effect vectors plus public action memory therefore produced a material control gain with only ~565k new parameters.

This is important negative evidence: the bottleneck is no longer primarily action selection. **Longer imagination is mis-ranked.** Depth 2 helps `implicit_goal_regimes` but damages `regime_switch` and `causal_prerequisites`; depth 8 does not recover the loss. The next candidate should preserve the strong shallow policy and improve how imagined future states are valued, rather than adding generic capacity.

## Claim boundary

This result does not establish AGI, broad reasoning, or superiority to any large language model. It is a bounded closed-loop procedural result on FIGG-18 train worlds. Because the admission gate failed, R2.0e is not promoted to the current strongest deployment weight and DEV/FRESH are not opened.
