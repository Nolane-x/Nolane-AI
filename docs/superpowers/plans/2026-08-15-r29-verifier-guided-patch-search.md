# R2.9 Verifier-Guided Patch Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and lock a deterministic, verifier-guided, parameter-free search engine for concrete text patches.

**Architecture:** Represent immutable text edits and repository snapshots, evaluate candidates only through a sandbox/evaluator callback, cache canonical fingerprints, and perform deterministic best-first search with evidence-driven refinement. R2.8 graph risk informs ranking but terminal success is controlled only by executable verification.

**Tech Stack:** Python 3.11, dataclasses, hashlib, heapq, pytest; existing `cogcoder.r28_repo_world` for blast-radius evidence.

## Global Constraints

- Add exactly 0 neural parameters.
- Never accept a patch unless `VerificationResult.success` is true.
- Hard budget <= 8 evaluator calls per locked task.
- Candidate fingerprints are content-derived, not candidate-id-derived.
- No language id, task id, filename literal, or benchmark answer may control routing.
- External coding claims remain false.

---

### Task 1: Patch algebra and safe application

**Files:**
- Create: `cogcoder/r29_patch_model.py`
- Test: `tests/test_r29_patch_model.py`

**Interfaces:**
- Produces: `TextEdit`, `RepositorySnapshot`, `PatchCandidate`, `apply_candidate()`, `patch_fingerprint()`.

- [ ] Write failing tests for valid edits, overlap rejection, invalid span rejection, deterministic fingerprints, and id-renaming invariance.
- [ ] Run `PYTHONPATH=. pytest -q tests/test_r29_patch_model.py` and confirm RED.
- [ ] Implement immutable patch model and canonical fingerprinting.
- [ ] Re-run the test and confirm GREEN.

### Task 2: Verification evidence and search memory

**Files:**
- Create: `cogcoder/r29_patch_search.py`
- Test: `tests/test_r29_patch_search.py`

**Interfaces:**
- Produces: `VerificationResult`, `PatchSearchMemory`, `PatchSearchTrace`, `PatchSearchOutcome`, `VerifierGuidedPatchSearch`.
- Consumes: R2.9 patch model and optional `RepoWorldGraph`.

- [ ] Write failing tests for deduplication, budget enforcement, deterministic ordering, false-terminal rejection, and low-blast-risk ranking.
- [ ] Run the focused tests and confirm RED.
- [ ] Implement memory, utility, deterministic best-first queue, and terminal verification rules.
- [ ] Re-run and confirm GREEN.

### Task 3: Execution-driven refinement protocol

**Files:**
- Create: `benchmarks/codeworld/r29_patch_cases.py`
- Test: `tests/test_r29_protocol.py`

**Interfaces:**
- Produces: `locked_r29_cases()` with exactly four preregistered tasks; each task supplies initial candidates, evaluator, refinement callback, graph, and expected successful patch fingerprint.

- [ ] Write protocol tests that assert four cases, <=8 budget, candidate-id rename invariance, and no answer leakage fields.
- [ ] Implement hidden-fix micro repositories and decoy/refinement candidates.
- [ ] Run protocol tests to GREEN.

### Task 4: Locked measurement and claim boundary

**Files:**
- Create: `research/R2_9_PRE_DEV_LOCK.json`
- Create: `scripts/measure_r29_patch_search.py`
- Test: `tests/test_r29_measure.py`

**Interfaces:**
- Measurement emits JSON with solve count, false accepts, duplicate evaluator calls, rename invariance, max evaluator calls, parameter count, and claim boundary.

- [ ] Write the lock before reading measurement output.
- [ ] Write failing measurement-contract test.
- [ ] Implement measurement script and run it once.
- [ ] Accept Phase A only if all locked thresholds pass; otherwise record rejection without changing thresholds.

### Task 5: Delivery, CI, and regression

**Files:**
- Create: `.github/workflows/r29-patch-search.yml`
- Create: `archive/root-history/historical_r_series/R2_9_DELIVERY.md`
- Create: `archive/root-history/historical_r_series/R2_9_RELEASE_MANIFEST.json`
- Modify: `README.md`

**Interfaces:**
- CI runs R2.8 + R2.9 focused tests, lock validation, measurement reproduction, compileall, and uploads a full source snapshot artifact.

- [ ] Add CI and delivery docs with explicit external-claim lock.
- [ ] Run R2.8+R2.9 tests, measurement, and compileall on the exact tree.
- [ ] Verify 0 neural parameter increase.
- [ ] Integrate atomically to `main` and inspect GitHub Actions evidence.
