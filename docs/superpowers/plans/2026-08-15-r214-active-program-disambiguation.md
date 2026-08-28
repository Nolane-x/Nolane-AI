# R2.14 Active Program Disambiguation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace shortest-consistent commitment with a bounded semantic version-space identifier that actively queries discriminating inputs and abstains when ambiguity remains.

**Architecture:** Enumerate observational equivalence classes over a frozen finite probe domain, filter them by demonstrations, then choose minimax discriminator inputs under a hard oracle budget. Keep evidence immutable and expose deterministic diagnostics for preregistered evaluation.

**Tech Stack:** Python 3.11 standard library, pytest, existing `cogcoder.epistemic_program` instruction semantics and R2.3 synthesis baseline.

## Global Constraints

- R2.14 adds exactly 0 neural parameters; total stays 79,450,489.
- Do not modify R2.13 frozen heldout result or thresholds.
- Do not inspect heldout outcomes before source/protocol lock.
- Oracle budget <= 3 on accepted heldout tasks.
- Resolve only a unique observational equivalence class; otherwise certify equivalence or abstain.
- Candidate/program names cannot influence query choice or result.

---

### Task 1: Semantic version-space core

**Files:**
- Create: `tests/test_r214_version_space.py`
- Create: `cogcoder/r214_active_synthesis.py`

**Interfaces:**
- Produces `ProgramHypothesis`, `SemanticClass`, `VersionSpace`, `ActiveIdentificationResult`, `ActiveProgramIdentifier`.

- [ ] Write failing tests for retaining distinct semantics despite identical sparse-demo behavior, equivalence collapse, and conflicting demos.
- [ ] Run tests and confirm RED because R2.14 module is absent.
- [ ] Implement bounded signature enumeration and demonstration filtering.
- [ ] Run tests and confirm GREEN.

### Task 2: Active discriminator and evidence trace

**Files:**
- Modify: `tests/test_r214_version_space.py`
- Modify: `cogcoder/r214_active_synthesis.py`

**Interfaces:**
- Produces deterministic `select_discriminator()` and `identify()` with immutable observation trace.

- [ ] Add RED tests for minimax split choice, <=3 oracle calls, budget abstention, no-query equivalence certificate, and permutation invariance.
- [ ] Implement minimal query/update loop.
- [ ] Run focused tests GREEN.

### Task 3: Multi-family benchmark and baselines

**Files:**
- Create: `benchmarks/kfigg/r214_program_identification.py`
- Create: `tests/test_r214_protocol.py`
- Create: `scripts/run_r214_program_identification.py`

**Interfaces:**
- Produces deterministic DEV/heldout task suites and aggregate metrics for active, shortest-consistent, passive-fixed, and random-budgeted modes.

- [ ] Write RED protocol tests for family diversity, seed separation, ambiguity construction, equal query budgets, abstention cases, and identity perturbation.
- [ ] Implement benchmark/task generator and runner.
- [ ] Run protocol tests GREEN.

### Task 4: DEV falsification and preregistration

**Files:**
- Create: `research/R2_14_DEV_RESULT.json`
- Create: `research/R2_14_PRE_HELDOUT_LOCK.json`

- [ ] Run at least five DEV seeds and record per-seed metrics.
- [ ] If DEV exposes a design flaw, fix it under TDD and rerun DEV; DEV is tunable.
- [ ] Once stable, freeze source SHA-256, benchmark parameters, heldout seed range, thresholds, and neural count.
- [ ] Run tests validating the lock against source bytes.

### Task 5: One-shot heldout and decision

**Files:**
- Create: `research/R2_14_PHASE_A_RESULT.json`
- Create: `archive/root-history/historical_r_series/R2_14_DELIVERY.md`
- Modify: `README.md` only if outcome/claim boundary needs recording.

- [ ] Run the frozen heldout once.
- [ ] Compute all preregistered gate fields without changing thresholds.
- [ ] Mark `accepted` only if every gate passes; otherwise `rejected`.
- [ ] Record AGI engineering-readiness delta conservatively.

### Task 6: Verification, GitHub, package, Library

**Files:**
- Create: `.github/workflows/r214-active-program-disambiguation.yml`
- Create: `archive/root-history/historical_r_series/R2_14_RELEASE_MANIFEST.json`

- [ ] Run R2.14 focused tests, current root `tests/`, and compileall.
- [ ] Verify frozen source hashes and no R2.13 history rewrite.
- [ ] Seal exact source/result to GitHub `main` with non-force fast-forward.
- [ ] Check CI; if account billing still prevents runner assignment, record infrastructure-blocked rather than success.
- [ ] Build COMPLETE ZIP with full project, artifacts, tests, docs, locks, results, provenance, and checksums.
- [ ] Validate ZIP `testzip`, hashes, and required entries.
- [ ] Upload COMPLETE ZIP to ChatGPT Library.
