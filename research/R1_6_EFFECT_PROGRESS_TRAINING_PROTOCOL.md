# R1.6 Effect-to-Progress Critic — preregistered training and capability gate

Date: 2026-08-12 (Asia/Bangkok)

## Parent

`checkpoints/Nolane-R1.6-NS2-CurrentBest.pt`

The recovered machine decision makes `CurrentBest.pt` byte-identical to accepted `PSRPlanner.pt` (SHA-256 `594e19faaf07094532d86629457dd81322113f06f7a932e05b07367f3c5dbb90`). All parent weights are frozen.

## Train-only data isolation

Procedural `train` split only:

- families: causal identification, delayed resource, compositional rule
- fit indices: **82–91** per family (10 each)
- internal validation indices: **92–94** per family (3 each)
- seed: **16120**
- R1.6 fresh remains unopened

Only parameters under `effect_progress_critic.*` may receive gradients.

## Objective

The critic learns a residual on top of frozen CurrentBest logits from:

- current 128D public predictive-state sketch;
- contrastive 128D effect sketch of each action that has actually been observed;
- action observation counts.

Unobserved actions remain exact zero. No action IDs/names, hidden goal fields, oracle transitions, or benchmark-family identifiers enter the critic.

The candidate may proceed to closed-loop dev only if internal-validation cross-entropy improves and teacher-forced accuracy is not lower than the frozen parent. This internal metric is not itself a capability claim.

## Closed-loop capability gate

If internal validation passes, evaluate **without tuning after seeing results** on two disjoint held-out dev slices:

- slice A: dev indices **66–71** per family
- slice B: dev indices **72–77** per family

Control is `CurrentBest.pt`; candidate is the frozen EffectProgress checkpoint. Acceptance requires all three conditions:

1. candidate solved count is **not lower than control on either slice**;
2. candidate aggregate solved across both slices is **strictly greater** than control aggregate;
3. candidate aggregate `causal_identification` solved across both slices is **strictly greater** than control causal aggregate.

Otherwise the module is rejected and `CurrentBest.pt` remains unchanged. No fresh task is opened by this experiment.