# R1.6 RuleProgramPrior — second breadth continuation preregistration

Date: 2026-08-12 (Asia/Bangkok)

## Parent

Accepted CurrentBest = breadth-trained RuleProgramPrior + EffectProgress, SHA-256 `f3108d2e74f955c57578bb42baca5f33890545d07310ef05d239b48333911648`, effective params `72,260,609`.

No new parameters are introduced. Only existing `rule_program_*` parameters may receive gradients; every other parameter stays frozen.

## New train-only data

Fit:
- compositional-rule indices **148–187** (40 worlds)
- causal-identification indices **133–142** (10 worlds)
- delayed-resource indices **133–142** (10 worlds)

Internal validation:
- compositional-rule indices **208–217** (10 worlds)
- causal-identification indices **146–148** (3 worlds)
- delayed-resource indices **146–148** (3 worlds)

Seed: `16270`. Weighted CE remains rule=2.0, causal/resource=0.5. No dev/fresh data is used in optimization or selection.

## Internal gate

Proceed to closed-loop only if validation simultaneously has:
1. lower weighted CE than the frozen CurrentBest;
2. higher compositional-rule teacher accuracy;
3. non-lower causal teacher accuracy;
4. non-lower resource teacher accuracy;
5. non-lower overall teacher accuracy.

## Closed-loop gate

If internal gate passes, evaluate CurrentBest control versus frozen continuation candidate on:
- dev90–95 per family;
- dev96–101 per family.

Accept only if candidate is non-worse in total solved on each slice, strictly better in aggregate total solved and aggregate compositional-rule solved, and non-worse in aggregate causal/resource solved. Fresh remains unopened.