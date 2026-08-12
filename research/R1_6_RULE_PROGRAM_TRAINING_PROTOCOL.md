# R1.6 RuleProgramPrior — preregistered training and closed-loop gate

Date: 2026-08-12 (Asia/Bangkok)

## Parent

Accepted `checkpoints/Nolane-R1.6-NS2-CurrentBest.pt`, currently EffectProgressCritic, SHA-256 `0a1688062f7640739847070a54ea079a28c10c010b286c5b640645214e912ace`.

All parent parameters are frozen. Only `rule_program_*` parameters may receive gradients.

## Train-only data

- fit indices: **95–104** per family
- internal-validation indices: **105–107** per family
- seed: **16170**
- all three families are included so the learned applicability gate must preserve non-rule behavior rather than receiving a hard-coded family switch
- R1.6 fresh remains unopened

The residual sees only public context, dynamic enriched action embeddings, and recurrent public action counts. It receives no family label, fixed action ID, private rule program, or oracle state at inference.

## Internal gate

Candidate proceeds to closed-loop dev only if:

1. internal-validation cross-entropy is lower than frozen CurrentBest;
2. overall teacher-forced action accuracy is not lower;
3. compositional-rule teacher-forced action accuracy is **strictly higher**.

Teacher metrics alone are not a capability claim.

## Closed-loop gate

If internal gate passes, evaluate without tuning on two new disjoint dev slices:

- slice A: dev indices **78–83** per family
- slice B: dev indices **84–89** per family

Acceptance requires:

1. candidate total solved is not lower than control on either slice;
2. aggregate solved across both slices is strictly higher;
3. aggregate compositional-rule solved is strictly higher;
4. aggregate causal-identification solved is not lower;
5. aggregate delayed-resource solved is not lower.

Otherwise reject the module and retain the EffectProgress CurrentBest. Fresh stays closed.