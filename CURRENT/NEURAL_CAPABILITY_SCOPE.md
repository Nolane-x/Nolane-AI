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

## Current capability baseline

- Frozen neural capability asset: `model/neural-r2.3`.
- Physical parameter count of the accepted R2.3 neural asset: 79,858,099.
- R2.4 provides the current shared cognition / confidence / evidence contract around that asset; contract hardening is not automatically a new neural checkpoint.
- Future Neural Core work starts from this measured capability baseline and must publish neural-only evidence separately from hybrid-runtime evidence.

## Required evaluation ladder

Every future neural capability candidate must distinguish at least:

1. frozen parent neural-only;
2. candidate neural-only;
3. candidate neural + minimal generic tools;
4. candidate neural + full permitted External Core.

The Neural Core claim is authorized only by (1) versus (2). Hybrid gains from (3) or (4) are system-level evidence and may not be relabeled as neural gains.

## Anti-scope-drift rule

Do not extend an active Neural milestone into Evaluation, External Core, memory, execution, Assurance, Integration, or repository-governance work merely because those components consume neural outputs. If a blocking defect is found there, repair it under its own runtime/component scope, close it, and return to the Neural milestone.
