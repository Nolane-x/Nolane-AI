# R1.6 RuleProgramPrior — breadth-vs-architecture preregistration

Date: 2026-08-12 (Asia/Bangkok)

Purpose: distinguish insufficient procedural breadth from an architectural failure of the already-tested RuleProgramPrior. No new trainable module is introduced.

## Parent / optimizer

- parent: accepted EffectProgress `CurrentBest.pt` (SHA `0a1688062f7640739847070a54ea079a28c10c010b286c5b640645214e912ace`)
- only existing `rule_program_*` parameters are trainable (411,650 params)
- all EffectProgress, PSR, trunk, recurrent memory, world-model and base policy weights remain frozen
- seed: `16220`

## Train-only breadth

Rule-heavy fit:
- compositional-rule indices **108–187** (80 worlds)

Negative-preservation fit:
- causal-identification indices **108–127** (20 worlds)
- delayed-resource indices **108–127** (20 worlds)

Internal validation, disjoint from fit:
- compositional-rule indices **188–207** (20 worlds)
- causal-identification indices **128–132** (5 worlds)
- delayed-resource indices **128–132** (5 worlds)

No dev/fresh task participates in optimization or model selection.

## Loss / selection

Teacher action CE is weighted toward the target bottleneck: rule rows weight 2.0, causal/resource rows weight 0.5. This does not provide any family label at inference; family is used only to balance train-only supervision.

A candidate may proceed to closed-loop dev only if the held-out train-only validation simultaneously shows:

1. compositional-rule teacher accuracy strictly above CurrentBest baseline;
2. causal teacher accuracy not lower;
3. resource teacher accuracy not lower;
4. overall teacher accuracy not lower;
5. weighted validation CE lower.

If breadth cannot satisfy this internal gate, RuleProgramPrior is rejected as an architectural dead end for R1.6 and no dev slice is opened.