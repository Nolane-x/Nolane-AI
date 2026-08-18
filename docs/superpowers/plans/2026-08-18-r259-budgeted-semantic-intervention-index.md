# R2.59 Budgeted Semantic Intervention Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Amortize R2.58 intervention probe synthesis through a deterministic semantic index and enforce a hard global synthesis budget without weakening causal verification.

**Architecture:** Reuse R2.58 positional interventions and R2.57 promoted vocabulary. Build one semantic probe index per free-position projection, exact-lookup intervention target vectors, validate hits, cache downstream synthesis by seed digest, and fail closed on a global candidate budget.

**Tech Stack:** Python 3.11/3.13, pytest, Nolane-AI R2.57/R2.58 cognitive runtime, GitHub Actions, Nolane World 0.8.0.

**Spec:** `docs/superpowers/specs/2026-08-18-r259-budgeted-semantic-intervention-index-design.md`

## Global Constraints
- Zero new trainable parameters.
- Preserve positional/rename invariance and strict I/O-only oracle boundary.
- No separate task-specific intervention anchor argument in the primary R2.59 discovery API.
- Hard global synthesis-candidate budget; fail closed on exhaustion.
- R2.58→R2.41 protected lineage must remain green.
- R2.59 external ufunclab evidence is matched-distribution efficiency evidence only.

---

### Task 1: Semantic index and budget ledger
**Files:** Create `cogcoder/r259_semantic_intervention_index.py`; Test `tests/test_r259_semantic_intervention_index.py`.

- [ ] Write failing tests for anchor derivation, semantic-vector canonicalization, deterministic positional reuse, index reuse and global budget exhaustion.
- [ ] Run focused tests and verify RED for missing R2.59 module/API.
- [ ] Implement the minimal semantic index, cache and ledger.
- [ ] Run focused tests to GREEN and commit.

### Task 2: Causal downstream verification
**Files:** Modify `cogcoder/r259_semantic_intervention_index.py`; Test `tests/test_r259_semantic_intervention_index.py`.

- [ ] Add failing tests requiring disjoint probe validation, learned-abstraction use, no-seed failure, unique-seed downstream caching and invalid-oracle abstention.
- [ ] Run RED.
- [ ] Implement minimal causal validation and cached downstream synthesis.
- [ ] Run GREEN and commit.

### Task 3: Frozen efficiency benchmark
**Files:** Create `benchmarks/kfigg/r259_budgeted_semantic_intervention_index.py`, `tests/test_r259_budgeted_semantic_intervention_benchmark.py`, `R2_59_PHASE_A_RESULT.json`.

- [ ] Write frozen benchmark tests with rename/permutation and efficiency thresholds.
- [ ] Verify RED.
- [ ] Implement benchmark, run it, freeze exact result, then verify exact recomputation.
- [ ] Commit.

### Task 4: External matched-distribution efficiency transfer
**Files:** Create `research/r259_external_budgeted_intervention_transfer.py`, `tests/test_r259_external_budgeted_intervention_transfer.py`.

- [ ] Write fixture-driven tests requiring no separate anchor list, no-seed fail, seeded solve, 8/8 challenge, 24/24 heldout and hard global budget.
- [ ] Verify RED.
- [ ] Implement harness and run against a local compatible oracle fixture.
- [ ] Commit.

### Task 5: Hosted verification and release boundary
**Files:** Create `.github/workflows/r259-budgeted-semantic-intervention-index.yml`, `R2_58_TO_R2_59_EVOLUTION.md`; after hosted evidence add release evidence files and release-bundle workflow.

- [ ] Run focused R2.59 and protected R2.58→R2.41 tests locally in bounded groups.
- [ ] Add Python 3.11/3.13 matrix and pinned ufunclab hosted job.
- [ ] Push an isolated R2.59 branch and require clean hosted evidence before acceptance.
- [ ] Run Nolane World W5 audit and preserve non-convergence unless earned.
- [ ] Freeze delivery, verify result, world result, manifest and complete ZIP only after hosted success.
