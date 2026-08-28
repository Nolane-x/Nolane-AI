# R2.58 Autonomous Intervention Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove R2.57's host-selected endpoint probe by adding deterministic, verified, causal pure-input intervention discovery.

**Architecture:** A positional intervention DSL enumerates reversible context rewrites without semantic labels. Each candidate must produce a non-constant vocabulary-synthesizable probe, verify on unseen probe contexts, and causally change downstream synthesis from failure to success under a matched frozen budget before it can be selected.

**Tech Stack:** Python 3.11/3.13, pytest, existing R2.56 expression DSL, R2.57 vocabulary/synthesis runtime, GitHub Actions, Nolane World 0.8.0.

**Spec:** `docs/superpowers/specs/2026-08-18-r258-autonomous-intervention-discovery-design.md`

## Global Constraints
- Zero new trainable parameters.
- I/O-only target oracle access.
- No semantic-name dependence in intervention generation or ranking.
- Pure, reversible input-context rewrites only.
- Probe validation and causal downstream utility are mandatory promotion gates.
- Challenge/heldout data cannot participate in intervention selection.
- Preserve R2.57 and protected lineage behavior.

---

### Task 1: Positional intervention DSL

**Files:**
- Create: `tests/test_r258_intervention_discovery.py`
- Create: `cogcoder/r258_intervention_discovery.py`

**Interfaces:**
- Produces: `InterventionSpec`, `enumerate_interventions`.

- [ ] Write tests that require content-addressed positional IDs, rename-invariant enumeration, distinct field positions/anchors, and copy-on-apply semantics.
- [ ] Run focused tests and verify they fail because the R2.58 module does not exist.
- [ ] Implement the minimum positional DSL to satisfy the tests.
- [ ] Run the focused tests and verify PASS.

### Task 2: Probe evaluation and causal selection

**Files:**
- Modify: `tests/test_r258_intervention_discovery.py`
- Modify: `cogcoder/r258_intervention_discovery.py`

**Interfaces:**
- Produces: `InterventionDiscoveryReceipt`, `InterventionCandidateReceipt`, `discover_causal_intervention`.

- [ ] Add failing tests for constant-output rejection, unseen probe validation, non-causal rejection, deterministic selection, and matched no-seed-vs-seeded downstream gating.
- [ ] Run focused tests and verify the expected missing-symbol/behavior failures.
- [ ] Implement candidate evaluation with existing R2.57 synthesis functions and exact accounting.
- [ ] Run focused tests and verify PASS.

### Task 3: Frozen authored benchmark

**Files:**
- Create: `benchmarks/kfigg/r258_autonomous_intervention_discovery.py`
- Create: `tests/test_r258_autonomous_intervention_benchmark.py`

**Interfaces:**
- Produces: `run_benchmark() -> dict[str, object]`.

- [ ] Write a failing frozen benchmark test requiring success across three renamings plus one argument-order permutation, zero false accepts, causal no-seed failure/seeded success, and zero trainable parameters.
- [ ] Verify RED.
- [ ] Implement the benchmark with opaque role maps and frozen contexts/budgets.
- [ ] Verify GREEN and freeze the deterministic result to `archive/root-history/historical_r_series/R2_58_PHASE_A_RESULT.json` only after repeat-run equality.

### Task 4: External I/O-only transfer

**Files:**
- Create: `research/r258_external_intervention_transfer.py`
- Create: `tests/test_r258_external_intervention_transfer.py`

**Interfaces:**
- Produces: `run_external_transfer(oracle, source_id, source_commit) -> dict[str, object]`.

- [ ] Add failing tests with a local oracle stand-in proving the harness does not inject a selected endpoint probe.
- [ ] Verify RED.
- [ ] Implement generic positional intervention search over the finite anchor set and reuse the discovered seed for full synthesis.
- [ ] Verify local GREEN and exact 8/8 challenge, 24/24 heldout behavior on the stand-in.

### Task 5: Hosted verification and release boundary

**Files:**
- Create: `.github/workflows/r258-autonomous-intervention-discovery.yml`
- Create: `archive/root-history/historical_r_series/R2_57_TO_R2_58_EVOLUTION.md`
- Create after hosted evidence: `archive/root-history/historical_r_series/R2_58_DELIVERY.md`, `archive/root-history/historical_r_series/R2_58_VERIFY_RESULT.json`, `archive/root-history/historical_r_series/R2_58_WORLD_FINAL.json`, `archive/root-history/historical_r_series/R2_58_RELEASE_MANIFEST.json`.
- Modify: `archive/root-history/historical_r_series/R2_READINESS_RECALIBRATION.md` only if independent hosted evidence passes.

**Interfaces:**
- Hosted CI installs pinned ufunclab and runs R2.58 plus protected parent regressions.

- [ ] Run all local R2.58 tests and R2.57→R2.41 protected lineage tests.
- [ ] Add Python 3.11/3.13 focused matrix and pinned ufunclab external transfer job.
- [ ] Push the implementation branch and require hosted external evidence before claiming acceptance.
- [ ] Run Nolane World W5 adversarial audit; preserve W5=false if convergence is not earned.
- [ ] Freeze release evidence and only then update readiness conservatively.
