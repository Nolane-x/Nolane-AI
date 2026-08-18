# R2.60 Complementary Causal Experiment Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and externally verify a bounded two-experiment causal program that solves a target only through complementary verified probes under matched synthesis budget.

**Architecture:** Reuse positional interventions from R2.58 and finite-anchor derivation discipline from R2.59. Discover pair structure from oracle-output semantics first, then synthesize only the two selected probes, compose them with the discovered operation, and verify proper-subset failure plus full-program success on disjoint evidence.

**Tech Stack:** Python 3.11/3.13, pytest, existing Nolane-AI symbolic DSL, GitHub Actions, pinned ufunclab, Nolane World 0.8.0.

**Spec:** `docs/superpowers/specs/2026-08-18-r260-complementary-experiment-program-design.md`

## Global Constraints
- Zero new trainable parameters.
- Pure input interventions only; no filesystem/network/process/time/random effects.
- Positional/content-addressed identities independent of semantic field names.
- Finite host-declared numeric composition operations only.
- Disjoint discovery and validation contexts.
- Flat baseline candidate budget >= sum of selected probe candidate budgets.
- External learner source exposure is I/O only.
- W5 convergence is fail-closed and may remain false.

---

### Task 1: Core complementary-program discovery
**Files:** create `tests/test_r260_complementary_experiment_program.py`, then create `cogcoder/r260_complementary_experiment_program.py`.
- [ ] Write tests for exact complementary pair discovery, singleton rejection, invalid-intervention fail-closed behavior, rename invariance, and deterministic program identity.
- [ ] Run focused tests and confirm RED because the R2.60 module does not exist.
- [ ] Implement minimal profile and pair-search core.
- [ ] Run focused tests and confirm GREEN.

### Task 2: Matched-budget hierarchical probe synthesis
**Files:** extend the same test/core files.
- [ ] Add a failing test where each depth-2 probe is synthesizable, the direct target flat baseline fails under the summed candidate budget, and their discovered composition validates exactly.
- [ ] Implement post-discovery two-probe synthesis and composed-expression validation.
- [ ] Verify singleton expressions are non-exact against the target and full expression is exact.

### Task 3: Frozen authored benchmark
**Files:** create `benchmarks/kfigg/r260_complementary_experiment_program.py`, `tests/test_r260_complementary_benchmark.py`, `R2_60_PHASE_A_RESULT.json`.
- [ ] Write benchmark-contract test first and confirm RED.
- [ ] Implement deterministic configurations including a rename replay and role permutation.
- [ ] Freeze exact Phase-A JSON only after recomputation matches twice.

### Task 4: New external function-family transfer
**Files:** create `research/r260_external_complementary_transfer.py`, `tests/test_r260_external_complementary_transfer.py`.
- [ ] Write local oracle-double tests first and confirm RED.
- [ ] Implement opaque-field I/O-only harness for the deadzone family with host-declared input-validity constraint.
- [ ] Verify local challenge/heldout, proper-subset failure, no host-selected intervention, and strict source-exposure metadata.

### Task 5: Hosted verification and lineage
**Files:** create `.github/workflows/r260-complementary-experiment-program.yml` and pre-host lock.
- [ ] Run local R2.60 tests plus protected R2.59/R2.58/R2.57 parents.
- [ ] Push branch and run GitHub Actions on Python 3.11/3.13.
- [ ] Install pinned ufunclab from commit `f1fbe6769850823a1976ccc28d14cd966130b645` and execute the actual `ufunclab.deadzone` transfer.
- [ ] Require hosted Phase-A exact recomputation and external evidence before acceptance.

### Task 6: Nolane World audit and release
- [ ] Feed implementation, falsifiers, local/hosted evidence, and unresolved unknowns into the W5 world.
- [ ] Preserve W5=false unless its gate actually passes.
- [ ] Freeze verify/world/manifest/readiness evidence conservatively.
- [ ] Create complete repository release ZIP from final main, SHA-256 it, run `unzip -tq`, upload workflow artifact, and persist release artifact/checksum to Library.
