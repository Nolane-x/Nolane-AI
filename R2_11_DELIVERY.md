# Nolane R2.11 — Differential Multi-File Localization

Date: 2026-08-15  
Status: **PHASE-A INTERNAL MULTI-FILE GATE ACCEPTED / EXTERNAL REPOSITORY GATES PENDING**

## Capability added

R2.11 adds **0 neural parameters**. It separates repository fault localization from patch proposal:

`coverage + runtime behavior + R2.8 graph -> localized symbol -> R2.10 copy-edit proposal -> R2.9 execute/verify`

The localizer uses no filename, node-id, language-id, task-id, candidate-id, or gold-location feature. Paths/IDs are routing handles only.

## Negative result retained

Before the final design, using R2.10 edit-gain as the localizer produced weak DEV Hit@1 (56.25%, then 34.38% after per-symbol evidence routing). Ablation showed localization-specific execution evidence was superior, so R2.10 edit-gain is disabled in the accepted R2.11 localizer.

## Locked protocol

The lock `research/R2_11_PRE_MEASURE_LOCK.json` (SHA-256 `9ab8a23c11e188481cc2416603d864bea27f11556d14eeef1237b4b9caa2df91`) freezes source hashes, thresholds, seed, 64 JavaScript repositories, 8 providers/repo, 2 off-path symbols, 8 coverage tests, a healthy spectrum-shadow provider, identity permutation, and patch budget 2.

## Heldout result

- localization Hit@1: **95.3125%**
- localization Hit@3: **100%**
- localization MRR: **97.65625%**
- spectrum-only baseline Hit@1: **62.5%**
- localization improvement: **+32.8125 pp**
- integrated verified solve: **92.1875%**
- spectrum baseline verified solve: **59.375%**
- solve improvement: **+32.8125 pp**
- identity permutation invariance: **100%**
- false terminal accepts: **0**
- max patch evaluations: **2**
- new neural parameters: **0**
- effective neural parameters remain **79,450,489**

Aggregate result SHA-256: `9374cada7b20334925c3b22478f8a19df8b0e1440b48571a893265a87e23e020`.
Detailed 64-row evidence is stored in the milestone artifact as `R2_11_PHASE_A_RESULT_DETAILED.json` (SHA-256 `d3073e4e679295878cf829e650d65b3c19f53c15099d59bfa10a3e33f7312eda`).

## What this means

R2.11 demonstrates that the compact stack benefits from explicit localization evidence rather than asking the neural patch proposer to solve a different task. The runtime can narrow a multi-file fault using public execution structure and then reuse existing proposal/verification machinery without growing the model.

## Remaining gap

The protocol is still internal and intentionally structured around peer implementations with observable coverage/runtime behavior. It does not prove localization on arbitrary real repositories or natural-language GitHub issues.

## Next research axis

**R2.12 Fresh Real-Repository Localization.** Lock recent repositories/issues, measure file/symbol localization first, compare against trace/lexical baselines, and only then test end-to-end repair. External coding claims remain disabled until that evidence exists.

## Claim boundary

R2.11 does not establish AGI, broad software-engineering competence, arbitrary code generation, real-world issue-resolution performance, or frontier-model parity.
