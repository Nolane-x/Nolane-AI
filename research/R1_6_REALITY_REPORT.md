# Nolane R1.6 Neural System-2 — Reality Report

Date: 2026-08-12 (Asia/Bangkok)

R1.6 attempted to move capabilities that R1.5 delegated to an external symbolic System-2 workspace into a modestly larger neural architecture. The ~50M trunk was retained while new neural modules were allowed under a 75M ceiling. Pre-fresh CurrentBest contains 72,260,609 effective parameters. This report does not claim AGI.

## Locked fresh evidence

Before fresh, source, evaluator, checkpoints, and all 60 fresh task IDs/seeds were locked in commit `52e31beb9a569051165d17a7d6eebbee4aac1e12`. No R1.6 source/checkpoint tuning occurred after fresh was opened.

| Checkpoint | Params | Total | Causal | Resource | Rule |
|---|---:|---:|---:|---:|---:|
| PSRPlanner | 70,993,913 | 15/60 | 0/20 | 10/20 | 5/20 |
| EffectProgress | 71,848,959 | **28/60** | **2/20** | **20/20** | **6/20** |
| Pre-fresh CurrentBest / RuleProgramBroad | 72,260,609 | 23/60 | 1/20 | 20/20 | 2/20 |

Oracle control solves 60/60. Ten deterministic random repeats average 1.8/60 (3%).

EffectProgress versus PSRPlanner is a clean paired gain: **13 gained, 0 lost** (causal +2, resource +10, rule +1). This is the clearest R1.6 generalization result.

RuleProgramBroad versus EffectProgress is **1 gained, 6 lost**. Five of the six losses are compositional-rule tasks. Therefore its dev-gate improvement did not replicate on fresh and is classified as dev overfitting. R1.6 is not retuned after this result.

## What genuinely improved

- Predictive State Representation replaced catastrophic unconstrained latent rollout with a public structured predictive state.
- PSR planning produced real held-out dev gains before fresh.
- Effect-to-Progress Critic (~98.8k new trainable parameters) generalized strongly. It relates current public predictive state to effects the agent has actually observed, without fixed action IDs; unseen actions receive no effect bonus.

## Remaining gaps

- Opaque causal system identification remains weak: strongest locked fresh result is 2/20.
- Compositional rule induction remains weak: strongest locked fresh result is 6/20.
- Delayed-resource planning is strong on this benchmark (20/20 under EffectProgress).
- Offline teacher-forced accuracy repeatedly failed as a reliable proxy for closed-loop intelligence.
- More recurrent depth often increased compute without reliable capability gain.

## Verification

Post-fresh immutable verification:
- locked source/checkpoint hashes: PASS
- R1.6 + evaluator focused tests: **63/63 PASS**
- R1.1/R1.2 + benchmark-integrity regressions: **33/33 PASS**

The historical full suite did not finish inside the execution cap. It reached 19% and exposed two deterministic failures in `tests/test_effect_progress_critic.py`. Root cause is source/test contract drift: `neural_system2.py` contains two historical classes named `EffectProgressCritic`; the accepted checkpoint uses the later API (`sketch_dim`, explicit `action_counts`) while those two old standalone tests target the earlier API (`state_dim`, two-argument forward). This is intentionally **not fixed after fresh**, because source/tests are part of the pre-fresh hash lock. It belongs in R1.7 cleanup under new hashes/protocol.

## Scientific verdict

R1.6 contains a real neural capability improvement: **PSRPlanner 15/60 → EffectProgress 28/60** on locked first-seen tasks, with 13 paired gains and 0 paired losses. The version-number/pre-fresh winner was not the best fresh checkpoint; that negative result is preserved rather than hidden.

R1.6 fresh is now consumed. Any further training informed by these results must be R1.7+ and use a new untouched evaluation protocol/split.

For future R1.7 research, the strongest already-locked checkpoint on the consumed R1.6 fresh set is `Nolane-R1.6-NS2-EffectProgressCritic.pt`, SHA `0a168806...`, 71,848,959 parameters. Starting R1.7 from it is acceptable only if R1.6 fresh is never presented again as an untouched test.

Local full report SHA-256: `816c200e6a1586304f5cd471dced309b31ec67c836b9949811702b4bb9980771`.