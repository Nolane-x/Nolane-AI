# R2.57 Verified Cognitive Vocabulary Growth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Learn safe parameterized cognitive abstractions from verified R2.56 expressions and use the learned vocabulary to solve later tasks under a search budget that defeats the fixed R2.56 grammar.

**Architecture:** Add a pure parameterized template/call layer above R2.56, a compression-driven multi-task abstraction learner, and a vocabulary-aware enumerator that expands learned calls back to R2.56 expressions before evaluation. Promotion is lifecycle-gated and external transfer is I/O-only against a pinned `ufunclab.linearstep` oracle.

**Tech Stack:** Python 3.11/3.13, dataclasses, existing R2.53/R2.55 lifecycle/registry, R2.56 expression DSL, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-18-r257-verified-cognitive-vocabulary-growth-design.md`

## Global Constraints
- No arbitrary Python/code generation.
- No I/O, tool, filesystem, network, subprocess, clock, random, reflection, import, eval, or exec invention.
- Learned abstractions are pure, deterministic, content-addressed, acyclic and expansion-bounded.
- Promotion requires multi-task support, positive compression and exact held-out challenge agreement.
- External learner receives only oracle I/O, never external source text/AST.
- Preserve R2.56→R2.41 parent behavior and cross-Python determinism.
- Added trainable parameters: 0.

---

### Task 1: Parameterized Vocabulary Core

**Files:**
- Create: `cogcoder/r257_vocabulary.py`
- Create: `tests/test_r257_vocabulary.py`

**Interfaces:**
- Consumes: `Expr`, `Field`, `Const`, `Unary`, `Binary`, `IfElse`, `evaluate_expr`, `expr_digest` from R2.56.
- Produces: `TemplateParam`, `LearnedAbstraction`, `AbstractionCall`, `CognitiveVocabulary`, `expand_expr()`, `evaluate_with_vocabulary()`.

- [ ] Write failing tests that assert capture-free parameter substitution, deterministic content digests, recursive/cyclic abstraction rejection, missing-argument rejection, expansion-node budget rejection, and equivalence between expanded and direct R2.56 evaluation.
- [ ] Run `python -m pytest -q tests/test_r257_vocabulary.py`; verify RED due missing module/API.
- [ ] Implement the minimum pure template/call representation. `AbstractionCall` must never execute itself; `expand_expr()` substitutes into ordinary R2.56 nodes and rejects unknown IDs/cycles/budget overflow.
- [ ] Run `python -m pytest -q tests/test_r257_vocabulary.py`; require all GREEN.

### Task 2: Compression-Driven Abstraction Learning

**Files:**
- Create: `cogcoder/r257_library_learning.py`
- Create: `tests/test_r257_library_learning.py`

**Interfaces:**
- Consumes: verified `(task_id, Expr)` corpus and Task 1 vocabulary types.
- Produces: `VerifiedExpression`, `AbstractionCandidate`, `AbstractionLearningReceipt`, `learn_abstractions()`, `promote_abstraction()`.

- [ ] Write failing tests for structural anti-unification across opaque field names, repeated-variable equality preservation, minimum distinct-task support, strictly positive MDL compression, deterministic ranking, held-out challenge failure quarantine, and digest collision fail-closed.
- [ ] Run the focused tests and verify RED.
- [ ] Implement subtree extraction, structural grouping, anti-unification, argument extraction, compression accounting and lifecycle-gated promotion. Semantic labels/task names must not participate in ranking.
- [ ] Run Task 1+2 tests; require GREEN.

### Task 3: Vocabulary-Aware Synthesis

**Files:**
- Create: `cogcoder/r257_vocabulary_synthesis.py`
- Create: `tests/test_r257_vocabulary_synthesis.py`

**Interfaces:**
- Consumes: `OperatorExample`, `OperatorInventionNeed`, promoted `CognitiveVocabulary`.
- Produces: `VocabularySynthesisReceipt`, `synthesize_with_vocabulary()` and a comparable `synthesize_base_with_budget()` baseline.

- [ ] Write RED tests where R2.56 base grammar cannot reach a composed expression within a frozen `max_depth/max_candidates`, but the learned abstraction can; assert equal I/O truth set and explicit candidate accounting.
- [ ] Implement depth-layered enumeration with promoted abstraction calls as grammar productions; semantically deduplicate candidates on current examples; expand before evaluation; preserve deterministic rank.
- [ ] Add live-revocation test: a post-promotion counterexample must quarantine/remove the learned abstraction and restore working state.
- [ ] Run Task 1–3 tests; require GREEN.

### Task 4: Authored Benchmark and Independent External Transfer

**Files:**
- Create: `benchmarks/kfigg/r257_verified_vocabulary_growth.py`
- Create: `research/r257_external_vocabulary_transfer.py`
- Create: `tests/test_r257_verified_vocabulary_benchmark.py`
- Create: `tests/test_r257_external_vocabulary_transfer.py`

**Interfaces:**
- Authored benchmark outputs frozen metrics and learned digests.
- External harness accepts a callable oracle and never accepts source text.

- [ ] Write authored benchmark RED test requiring three unnamed learned abstractions (clamp-shaped, lerp-shaped, and normalize-shaped), positive compression, multi-task support, composed heldout exactness, R2.56 base 0 under same budget, bad-candidate quarantine and live revocation/rollback.
- [ ] Implement benchmark and freeze deterministic result.
- [ ] Write external harness RED test using a local callable with the `linearstep(x,a,b,fa,fb)` contract; assert base budget failure and vocabulary success on train/challenge/24+ heldouts.
- [ ] Implement I/O-only harness and source-exposure guard.
- [ ] Run all R2.57 tests and the R2.56 parent focused tests.

### Task 5: CI, World, Evidence and Release

**Files:**
- Create: `.github/workflows/r257-verified-vocabulary-growth.yml`
- Create after clean hosted acceptance: `R2_57_PHASE_A_RESULT.json`, `R2_57_EXTERNAL_TRANSFER.json`, `R2_57_VERIFY_RESULT.json`, `R2_57_WORLD_FINAL.json`, `R2_57_DELIVERY.md`, `R2_56_TO_R2_57_EVOLUTION.md`, `R2_57_RELEASE_MANIFEST.json`.
- Modify: `R2_READINESS_RECALIBRATION.md` only after evidence exists.
- Create: `.github/workflows/r257-release-bundle.yml`.

**Interfaces:**
- Hosted workflow installs pinned `WarrenWeckesser/ufunclab@f1fbe6769850823a1976ccc28d14cd966130b645`, calls `ufunclab.linearstep` only as oracle, uploads evidence, runs R2.56→R2.41 lineage and Python 3.11/3.13 matrix.

- [ ] Run local R2.57 + protected lineage in process groups; count exact passes.
- [ ] Publish a clean capability candidate to a branch/main only after byte/content verification.
- [ ] Require clean GitHub hosted R2.57 focused, external oracle, full protected lineage, frozen recomputation, and cross-Python statuses to be success.
- [ ] Run Nolane World adversarial audit; preserve W5 failure if critical unknowns remain.
- [ ] Set readiness conservatively from evidence, not architecture novelty.
- [ ] Create release commit/workflow that verifies frozen boundary and focused regressions, archives `HEAD`, writes SHA-256, runs `unzip -tq`, uploads `Nolane-AI-R2.57-COMPLETE`.
- [ ] Independently download/check artifact, persist ZIP + checksum + evidence to Library, and verify Library listing.
