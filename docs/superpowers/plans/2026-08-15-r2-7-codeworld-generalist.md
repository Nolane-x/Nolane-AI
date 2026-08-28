# R2.7 CodeWorld Generalist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Nolane from ARC-centric abstraction work toward compact, general software-engineering intelligence while keeping the neural core below 80M effective parameters in Phase A.

**Architecture:** Preserve the accepted 78,779,253-parameter R2.0i/R2.4 parent and add one small language/task-agnostic CodeWorld controller. The controller does not memorize source patches; it ranks generic coding-loop actions from structured repository/test/diff feedback. A deterministic safety layer blocks premature finish and forces recovery after high-risk regressions. External coding benchmarks remain evaluation-only and are never used as hidden-test training data.

**Tech Stack:** Python 3.11+, PyTorch, pytest, GitHub Actions.

## Global Constraints

- Target domain is broad software development, not ARC-specific optimization.
- Parameter growth must remain small; Phase A ceiling is 80,000,000 effective parameters.
- Parent checkpoint SHA-256 must remain bound in every R2.7 bundle.
- Train and held-out curriculum splits must be disjoint by `(language, task_type)` pair.
- No claim of broad coding competence, AGI, or external benchmark improvement is allowed before external gates run.
- Finish is illegal until targeted tests, full tests, and diff review are all complete.

---

### Task 1: Compact CodeWorld neural controller

**Files:**
- Create: `cogcoder/r27_codeworld_controller.py`
- Test: `tests/test_r27_codeworld_controller.py`

**Interfaces:**
- Consumes: structured state `[B,32]`, action features `[B,A,24]`, history `[B,T,16]`, language/task IDs and legal-action mask.
- Produces: masked action logits, stop logit and success logit.

- [x] Write tests that require variable action-set scoring, hard action masking, shape validation and <1M controller parameters.
- [x] Run tests and observe missing-module RED.
- [x] Implement a 192-wide recurrent fusion controller.
- [x] Verify controller tests pass.

### Task 2: Test-driven coding-loop safety runtime

**Files:**
- Create: `cogcoder/r27_codeworld_runtime.py`
- Test: `tests/test_r27_codeworld_runtime.py`

**Interfaces:**
- Consumes: `CodingLoopState` and scored `ActionProposal` values.
- Produces: legal action set and highest-scoring safe action.

- [x] Write failing tests for premature finish and regression recovery.
- [x] Implement legal-action gating and forced revert under high-risk tight-budget regressions.
- [x] Verify runtime tests pass.

### Task 3: Cross-language/task transfer curriculum

**Files:**
- Create: `cogcoder/r27_codeworld_curriculum.py`
- Test: `tests/test_r27_codeworld_curriculum.py`

**Interfaces:**
- Produces: controller rows across at least 8 languages and 6 task types.
- Split contract: whole `(language_id, task_type_id)` pairs are assigned either to train or held-out, never both.

- [x] Write failing coverage/isolation tests.
- [x] Implement deterministic curriculum generation and pair-disjoint split.
- [x] Verify split isolation.

### Task 4: Train, bind and measure the neural delta

**Files:**
- Create: `scripts/train_r27_codeworld_controller.py`
- Create: `scripts/measure_r27_codeworld.py`
- Test: `tests/test_r27_training.py`
- Test: `tests/test_r27_measure.py`

**Interfaces:**
- `train_controller(...) -> TrainingResult`
- `save_r27_bundle(parent_path, output_path, result) -> metadata`
- `evaluate_bundle(path, ...) -> report`

- [x] Write failing tests for held-out pair transfer and parent-SHA binding.
- [x] Train with deterministic seeds.
- [x] Package R2.7 as one weight carrying the original R2.0i payload plus the CodeWorld delta.
- [x] Reconstruct and re-evaluate the saved controller.

### Task 5: External CodeWorld evaluation contract

**Files:**
- Create: `benchmarks/codeworld/README.md`
- Create: `research/R2_7_PRE_DEV_LOCK.json`
- Create: `.github/workflows/r27-codeworld.yml`

- [x] Lock Phase-A scope before external benchmark tuning.
- [x] Define evaluation-only gates for issue repair, feature implementation, refactoring, terminal/tool use, multi-turn evolution and multilingual transfer.
- [x] Add CI for unit tests, bundle metadata checks and source snapshot artifact creation.

### Task 6: Delivery and claim boundary

**Files:**
- Create: `archive/root-history/historical_r_series/R2_7_DELIVERY.md`
- Create: `research/R2_7_PHASE_A_RESULT.json`
- Create: `archive/root-history/historical_r_series/R2_7_RELEASE_MANIFEST.json`

- [x] Record exact parameter count, hashes and internal transfer metrics.
- [x] State that Phase A is a compact controller milestone, not external coding proof.
- [ ] Run external CodeWorld gates in Phase B without training on benchmark hidden tests.
