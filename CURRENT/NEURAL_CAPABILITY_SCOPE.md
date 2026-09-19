# Neural Capability Work Scope

Status: current authority for distinguishing Neural Core capability work from runtime/evaluation hardening.

## Governing rule

A change counts as a **Neural Core capability upgrade** only when it changes at least one of:

- trainable neural architecture or neural parameters;
- learned internal representation or recurrent reasoning computation;
- neural training objective, curriculum, data mixture, optimizer/training procedure, or calibration procedure;
- learned neural policy for memory, tool, causal, planning, verification, or External Core interaction;
- neural checkpoint selection backed by a frozen neural-only evaluation;
- a neural-only capability result on a preregistered fresh/heldout gate.

Changes to serialization, restore validation, integer/finite-number canonicality, receipts, evidence ledgers, evaluation campaign plumbing, component revisions, CI, External Core protocols, or authority metadata do **not** count as Neural Core capability progress by themselves.

## Historical labeling correction

Recent commits labeled Neural R2.54 through R2.61 primarily hardened Evaluation, inference/runtime boundaries, and External Core execution types. They remain valid repository hardening work, but their labels must not be interpreted as eight generations of neural intelligence improvement.

The exact-integer restore closure following R2.61 is intentionally named as runtime hardening and receives no Neural R-number.

## Current neural capability authority

Two authorities are intentionally distinguished rather than conflated:

1. **Historical accepted baseline — R2.3**
   - path: `model/neural-r2.3`
   - physical parameter count: **79,858,099**
   - retained historical hashes/evidence remain valid provenance;
   - the original one-weight binary and 11,539-state expert/DAgger cache are not present in repository authority, so this lineage is not the source-reproducible training authority.

2. **Current source-reproducible accepted line — Neural vNext Native**
   - path: `model/neural-vnext-native`
   - authority: `model/neural-vnext-native/ACCEPTED_AUTHORITY.json`
   - physical parameter count: **334,099**
   - checkpoint SHA-256: `7de154972ed8e06aaf64064d4d1a6d3ee99331955b3ffb0cfdd8813643fb4f4b`
   - state-dict SHA-256: `ddd0e7d8744ed18c782febece06f419ec6fd339f62a5159fa1432b5a9d7c4098`
   - dev: **104/128**
   - untouched preregistered fresh court: **133/160 = 83.125%**
   - family fresh solves: conditional 36/40, regime-switch 31/40, implicit-goal 30/40, causal-prerequisites 36/40;
   - bitwise checkpoint/state reproduction passed before fresh opening;
   - post-fresh tuning for this candidate is forbidden.

R2.3 and Neural vNext Native used different fresh blocks/training programs. Their raw scores must not be treated as an apples-to-apples ranking. R2.3 remains historical accepted evidence; Neural vNext Native is the current accepted source-reproducible neural capability line.

R2.4 continues to provide shared cognition/confidence/evidence contracts around historical assets; contract hardening is not automatically a neural checkpoint upgrade.

## Required evaluation ladder

Every future neural capability successor must distinguish at least:

1. frozen parent neural-only;
2. candidate neural-only;
3. candidate neural + minimal generic tools;
4. candidate neural + full permitted External Core.

The Neural Core claim is authorized only by neural-only evidence. Hybrid gains from tool/runtime layers are system-level evidence and may not be relabeled as neural gains.

For a successor to Neural vNext Native, the candidate must be frozen before a new untouched fresh block is opened. Fresh indices already consumed by the accepted Native court (`fresh:0..39`) may not be reused as a promotion court.

## Anti-scope-drift rule

Do not extend an active Neural milestone into Evaluation, External Core, memory, execution, Assurance, Integration, or repository-governance work merely because those components consume neural outputs. If a blocking defect is found there, repair it under its own runtime/component scope, close it, and return to the Neural milestone.
