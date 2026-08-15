# R2.10 Compact Copy-Edit Proposer Design

Date: 2026-08-15
Status: approved under the standing autonomous research instruction

## Goal

Add a compact neural proposer that ranks language-agnostic structured copy/edit candidates from public code context and failure evidence, then delegates all execution and terminal acceptance to the unchanged R2.9 verifier-guided search.

## Why this milestone

R2.9 can search and refine supplied patches, but its proposal source is symbolic/manual. A free-form source decoder would consume the remaining parameter budget quickly and would make hallucinated code a new bottleneck. R2.10 instead learns a constrained proposal policy: choose *where to edit*, *which canonical edit family to apply*, and *which source token/span/operator to copy or substitute*. This makes the neural component responsible for ranking plausible minimal edits rather than generating arbitrary text.

## Research principles

1. **Preserve before generate.** Prefer minimal edits and copying existing source/context over open-ended token generation.
2. **Execution remains authoritative.** R2.10 may only influence candidate ordering; R2.9 execution/verification is the sole terminal-success authority.
3. **No language/task shortcut.** The proposer receives no `language_id`, `task_type_id`, benchmark family id, candidate id, or filename identity.
4. **Cross-language heldout.** Phase-A training uses Python-rendered tasks only; locked heldout evaluation uses JavaScript-rendered tasks only.
5. **Identifier invariance.** Identifier surface strings are canonicalized by role/position so systematic renaming cannot change candidate scores.
6. **Hard parameter ceiling.** Total effective parameters must remain below 80,000,000.

## Architecture

### 1. Canonical copy-edit vocabulary

A language adapter maps surface syntax into a small shared semantic token space:
- lexical roles: function, return, parameter, local identifier, numeric literal, boolean literal;
- canonical operators: ADD, SUB, MUL, LT, LE, GT, GE, EQ, NE, AND, OR;
- edit roles: replace-operator, replace-identifier, replace-literal, insert-copied-span, delete-span;
- source roles are position-based (`ARG0`, `ARG1`, `CONST0`, ...), not identifier names.

Surface rendering remains outside the neural model. The model scores structured candidates that already contain a legal surface patch.

### 2. Public failure evidence

Each task exposes one or more public failing probes. A fixed-size evidence vector records normalized numeric/boolean observations such as input values, expected value, observed buggy value, error sign/magnitude, boundary relation, and regression/history state. No hidden correct operator or gold-patch id is present.

### 3. Compact neural scorer

`CopyEditProposalNet` uses:
- one shared token embedding;
- one shared GRU encoder for buggy context and candidate replacement sequences;
- a small MLP for public evidence/history features;
- a fusion MLP and scalar candidate scorer.

The same token encoder is reused for Python and JavaScript canonical tokens. There are no language/task embeddings.

Target parameter budget: <= 300,000 new neural parameters, leaving a substantial margin under 80M total.

### 4. Training objective

Training rows are generated from clean Python micro-programs, then corrupted by one structured mutation. Candidate sets contain the inverse fix plus plausible decoys. Labels come from the hidden pre-mutation source only during training-data construction; the model input receives only buggy context, candidate structure, and public failure evidence.

Use listwise cross-entropy over candidates plus a small margin penalty encouraging the gold edit to outrank alternatives. Training examples are split by semantic template seed so heldout variants and identifier names are disjoint.

### 5. R2.9 integration

At inference:

`enumerate constrained candidates → R2.10 score/order → top candidates enter R2.9 → execute → refine/verify → accept or reject`

R2.10 cannot set `VerificationResult.success` and cannot bypass R2.9 regression checks.

## Locked Phase-A evaluation

Before training, freeze a heldout JavaScript panel generated from semantic families that also exist in training but with:
- JavaScript surface syntax only;
- disjoint identifiers and constants;
- disjoint template seeds;
- candidate ids randomized;
- no language/task id input.

Evaluate both:
1. **R2.10 proposer + R2.9**, execution budget 2 per task.
2. **Unranked deterministic baseline + R2.9**, same candidates and same budget.

Pre-registered acceptance:
- heldout JavaScript tasks: 48;
- R2.10 top-1 gold-candidate accuracy >= 75%;
- integrated verified solve rate under budget 2 >= 85%;
- improvement over same-budget unranked baseline >= 25 percentage points;
- identifier/candidate-id rename invariance >= 95%;
- false terminal accepts = 0;
- new neural parameters <= 300,000;
- total effective parameters < 80,000,000;
- external coding claim allowed = false;
- AGI claim allowed = false.

If any acceptance threshold fails, R2.10 Phase A is rejected without changing the frozen threshold.

## Checkpoint

On acceptance, append a `r210_copy_edit_delta` to the R2.7 one-weight bundle and save a new standalone checkpoint. The bundle records architecture, exact parameter count, training report, parent SHA, Phase-A lock/result SHA, and claim boundary.

## Claim boundary

Passing Phase A would establish only that a small neural scorer can improve constrained minimal-edit proposal ordering across a Python→JavaScript heldout surface transfer panel under executable verification. It would not establish arbitrary source-code generation, fresh-repository issue resolution, AGI, or frontier-model parity.

## Next axis if accepted

R2.11 should move from synthetic expression-level repair to fresh multi-file repository localization + proposal, retaining R2.8 world modeling and R2.9 verification. If cross-language proposal fails, investigate representation quality before increasing model size.
