# Nolane R2.10 — Compact Copy-Edit Proposer

Date: 2026-08-15  
Status: **PHASE-A INTERNAL CROSS-LANGUAGE GATE ACCEPTED / EXTERNAL CODING GATES PENDING**

## Why this milestone exists

R2.9 introduced verifier-guided patch search, but its candidate source was still symbolic/manual. R2.10 adds the first neural source-aware proposal layer in the coding track while preserving the compact-model constraint: the neural model ranks constrained copy/edit candidates instead of generating arbitrary source text.

The central design rule is **preserve/copy before free generation**. R2.10 chooses among minimal legal edits using canonical code structure and public failure evidence; R2.9 remains the sole execution and terminal-success authority.

## Architecture added

- language/task-id-free `CopyEditProposalNet`;
- shared canonical Python/JavaScript token space;
- identifier-role normalization (`ARG0`, `ARG1`, ...), removing surface-name shortcuts;
- canonical operator roles (ADD/SUB/MUL/DIV/LT/LE/GT/GE/...);
- fixed-size public failure-evidence encoding;
- shared embedding + GRU source/candidate encoder;
- evidence MLP + fusion scorer;
- constrained operator copy/edit enumeration;
- R2.9 execution verification under the same hard evaluator budget.

R2.10 does **not** contain `language_embedding`, `task_embedding`, language ids, task ids, candidate ids, or filename ids as neural inputs.

## Parameter accounting

- R2.9 parent effective parameters: **79,401,400**;
- R2.10 proposer: **49,089**;
- R2.10 effective neural parameters: **79,450,489**;
- hard project ceiling for this phase: **<80,000,000**.

Accepted standalone weight:

`Nolane-R2.10-Compact-Copy-Edit-Proposer-Phase-A-ONE-WEIGHT.pt`

- SHA-256: `508b4242dfa5103d1f444025d40419d1db7fa415172d81289f772b34de98c35d`

Recovery neural delta (stored in the milestone artifact, intentionally not committed to Git):

`R2_10_COPY_EDIT_DELTA.pt`

- bytes: **203,762**;
- SHA-256: `6373605fddb5f1cfe6e31d52958c0155443b2552dd1e4f3fdb8628d7ffab7e7f`.

GitHub CI retrains the proposer from the frozen source/seed and runs the heldout gate instead of trusting a committed binary state.

## Frozen protocol

The acceptance thresholds were stored before training-result inspection in `research/R2_10_PRETRAIN_LOCK.json`.

- training surface language: **Python only**;
- heldout surface language: **JavaScript only**;
- training rows: **384** (192 per semantic family);
- heldout executable cases: **48**;
- candidate execution budget: **2 per case**;
- same candidate set and same budget for proposer and baseline;
- identifiers/template seeds disjoint between training and heldout;
- systematic identifier/candidate-id rename invariance required;
- external coding and AGI claims disabled.

Pretrain-lock SHA-256:

`4930b327399ce6e205db648c20e4dd3d77a8afcca0f743bcfc7a116a3e664c3a`

## Locked Phase-A result

Measured after the lock was frozen:

- top-1 gold candidate accuracy: **91.67%**;
- R2.10 + R2.9 verified solve rate at budget 2: **93.75%**;
- unranked R2.9 baseline with identical candidates/budget: **50.00%**;
- improvement: **+43.75 percentage points**;
- identifier/candidate rename invariance: **100%**;
- false terminal accepts: **0**;
- new neural parameters: **49,089**;
- total effective parameters: **79,450,489**;
- Phase-A gate: **PASS**.

Committed result SHA-256:

`16f32e05a123b282dcc3f5fd034e6750a3edf5b34f2286561810be058ce7a7b2`

The committed aggregate is `research/R2_10_PHASE_A_RESULT.json`. Detailed 48-row evidence is persisted in the milestone artifact as `R2_10_PHASE_A_RESULT_DETAILED.json` (SHA-256 `1646efbcfe469d5f522f5bdc5ea28eead440bd8a30bdcaf8d29ef13b2d4aed81`). Re-measurement from the recovery delta reproduces both aggregate metrics and detailed rows; GitHub CI independently retrains from source and must satisfy the same frozen thresholds.

## What changed in capability

R2.9 could search supplied patches. R2.10 can now learn a small neural ordering policy over source-aware minimal edits and transfer that policy from Python training surfaces to JavaScript heldout surfaces because syntax and identifiers are canonicalized before scoring.

The learned proposer is not trusted to finish a task. Candidate scores only influence the R2.9 search order; executable tests and regressions still decide acceptance.

## Remaining gap

R2.10 is still expression-level constrained repair. It cannot yet localize arbitrary faults across a fresh multi-file repository, invent unrestricted code, understand broad natural-language issue descriptions, or synthesize large structural patches.

The next main research axis is **R2.11 Fresh Multi-File Localization + Proposal**: use R2.8 repository topology/epistemic hypotheses to choose a small source slice, then let R2.10 propose minimal edits inside that slice and R2.9 verify them. The key gate should use repositories/templates not used to build the localization heuristics.

## Claim boundary

R2.10 Phase A does not establish AGI, arbitrary code generation, broad repository repair, human-level software engineering, or frontier-model parity. It establishes a small cross-language constrained copy-edit proposal improvement under a frozen executable protocol.
