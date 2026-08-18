# R2.63 Compositional Version-Space Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend accepted R2.61 so a public refinement counterexample can justify a second trusted repository mutation while final verification stays disjoint and terminal.

**Architecture:** Reuse R2.60 compilation/minimax probing and R2.61 oracle-free trusted PatchMacro expansion. Maintain a public observation ledger, alternate active diagnosis with singleton refinement, compose bounded one-step mutations across depth, reject content cycles, and accept only after a separate heldout verification pool passes.

**Tech Stack:** Python 3.11/3.13, dataclasses, R2.47/R2.52/R2.60/R2.61 primitives, pytest, GitHub Actions, NumPy 2.4.6 for external I/O-only transfer.

**Spec:** `docs/superpowers/specs/2026-08-18-r263-compositional-version-space-expansion-design.md`

## Global Constraints

- Added trainable parameters: exactly 0.
- Candidate syntax/site generation has no oracle or target-output channel.
- Only pre-existing trusted R2.47 `PatchMacro` semantics may mutate repositories.
- Final verification is disjoint from all learning evidence and never triggers mutation.
- Hard budgets cover diagnostic calls, refinement calls, expansion rounds, depth, generated candidates and sites.
- Preserve every successful diagnostic/refinement observation in the public `PatchTest` ledger.
- Keep accepted R2.62/R2.61 and protected lineage green.

---

### Task 1: Hosted RED contract

**Files:** `tests/test_r263_compositional_version_space_expansion.py`, `.github/workflows/r263-compositional-repository-repair.yml`

**Interfaces:** consumes `RepositoryPatchCandidate`, `RepositoryProbe`, `PatchMacro`, R2.61 solver; defines expected `expand_compositional_frontier(...)` and `solve_repository_patch_with_compositional_expansion(...)`.

- [x] Write two-bug multi-file tests where R2.61 reaches a partial repair then terminally fails.
- [x] Add disjoint-refinement/final-verification and fail-closed contract tests.
- [x] Run hosted RED before the production module exists and record the contract-relevant `ModuleNotFoundError`.

### Task 2: Minimal compositional frontier and solver

**Files:** `cogcoder/r263_compositional_version_space_expansion.py`, `tests/test_r263_compositional_version_space_expansion.py`

**Interfaces:** consumes R2.60 `_compile_candidates`, `_filter_initial`, `_best_probe`, `_oracle_outcome`, `_outcome`; R2.61 `expand_repository_candidates`; content digests. Produces compositional frontier/round/receipt records and the solver.

- [x] Implement depth/provenance/content-state identity and seen-state rejection.
- [x] Implement oracle-free one-step frontier expansion.
- [x] Record every successful diagnostic/refinement label as public evidence.
- [x] Implement diagnosis → refinement → expansion → re-diagnosis loop with hard budgets.
- [x] Keep final verification terminal and non-recyclable.
- [x] Verify focused behavior on Python 3.11 and 3.13 with R2.62/R2.61 parent checks.

### Task 3: Authored causal benchmark

**Files:** `benchmarks/kfigg/r263_compositional_version_space_expansion.py`, `tests/test_r263_compositional_benchmark.py`, later `R2_63_PHASE_A_RESULT.json`.

**Interfaces:** consumes R2.61 baseline and R2.63 solver; produces deterministic Phase-A causal evidence.

- [x] Add structurally varied two-edit repository episodes.
- [x] Prove exact targets absent from initial and complete one-step content spaces.
- [x] Require R2.61 failure and R2.63 exact two-step success under matched authority.
- [x] Add depth/budget/missing-macro/oracle-error/terminal-verification/order/cycle adversarial gates.
- [ ] Freeze exact hosted Phase-A JSON and source blobs.

### Task 4: Independent external I/O-only transfer

**Files:** `research/r263_external_compositional_transfer.py`, `tests/test_r263_external_compositional_transfer.py`, later `R2_63_EXTERNAL_TRANSFER.json`.

**Interfaces:** consumes a callable only; produces exact external transfer receipt with separated oracle accounting.

- [x] Define a two-edit `Add -> Mult` repository wrapper for a square-function target, distinct from prior external families.
- [x] Keep exact target repository evaluation-only and absent from initial/one-step spaces.
- [x] Count R2.61 and R2.63 oracle calls without hidden post-hoc target calls.
- [ ] Run/freeze pinned NumPy 2.4.6 `numpy.square` hosted evidence.

### Task 5: Full lineage, Nolane World and release

**Files:** `R2_63_TDD_RED.json`, `R2_63_PRE_HOSTED_LOCK.json`, `R2_63_HOSTED_VERIFICATION.json`, `R2_63_WORLD_FINAL.json`, `R2_63_DELIVERY.md`, `R2_63_RELEASE_MANIFEST.json`, `R2_READINESS_RECALIBRATION.md`, `.github/workflows/r263-release-bundle.yml`.

- [ ] Freeze production/benchmark/external/test blobs against accepted R2.62 parent.
- [ ] Recompute exact Phase-A and external evidence on canonical PR merge tree.
- [ ] Run R2.63 focused/cross-Python and accepted R2.62→R2.41 protected lineage; record exact counts.
- [ ] Submit fresh hosted verifier evidence to Nolane World 0.8.0 and preserve W5 failure unless runtime requirements genuinely converge.
- [ ] Recalibrate readiness conservatively; score is an engineering heuristic, never AGI probability.
- [ ] Build and verify a complete repository ZIP gate with archive integrity and required-file checks.
- [ ] Merge only from current main, rerun post-merge bundle, independently verify the artifact, and persist ZIP + checksum to Library.
