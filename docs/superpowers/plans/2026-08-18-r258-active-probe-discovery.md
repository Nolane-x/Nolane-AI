# R2.58 Active Probe/Subgoal Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build bounded autonomous intervention/subgoal discovery that replaces R2.57's manually selected endpoint probe and causally unlocks vocabulary-aware full synthesis.

**Architecture:** Learn identity-exposing intervention schemas from existing R2.57 abstractions, compile them onto opaque task fields, query only a context-callable oracle, independently challenge latent candidates, and retain only candidates that unlock full synthesis under frozen budgets. Preserve deterministic fail-closed receipts and zero added trainable parameters.

**Tech Stack:** Python 3.11+, dataclasses, existing R2.56 pure expression DSL, R2.57 cognitive vocabulary/synthesis, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-18-r258-active-probe-discovery-design.md`

## Global Constraints
- Added trainable parameters: exactly 0.
- Oracle exposure: context-to-output I/O only; no source parsing or reflection.
- Any oracle/query/synthesis budget exhaustion fails closed.
- No AGI/general-program-synthesis claim.
- R2.57 focused regressions must remain green.

---

### Task 1: Exposure-schema discovery
**Files:**
- Create: `tests/test_r258_active_probe.py`
- Create: `cogcoder/r258_active_probe.py`

**Interfaces:**
- Consumes: `CognitiveVocabulary`, `AbstractionCall`, `Const`, `Field`, `evaluate_with_vocabulary`.
- Produces: `ExposureSchema`, `discover_exposure_schemas()`.

- [x] Write failing tests proving an identity-exposure schema is found generically for the learned lerp/normalize families and that schemas are content/slot based rather than semantic-name based.
- [x] Run `PYTHONPATH=. python -m pytest -q tests/test_r258_active_probe.py -k exposure`; confirm RED before implementation.
- [x] Implement deterministic finite-grid exposure validation, essential-control filtering, strict scalar checks and canonical schema ordering.
- [x] Re-run exposure tests; require GREEN.

### Task 2: Bounded intervention planner
**Files:**
- Modify: `tests/test_r258_active_probe.py`
- Modify: `cogcoder/r258_active_probe.py`

**Interfaces:**
- Produces: `ProbeBudget`, `ProbeAttemptReceipt`, `ActiveProbeReceipt`, `discover_verified_subgoal()`.

- [x] Add failing tests for autonomous field mapping, strict oracle-call accounting, budget exhaustion fail-closed behavior and invalid oracle outputs.
- [x] Verify new cases fail for missing behavior.
- [x] Implement canonical field-profile mapping, transformed-context oracle queries, challenged latent synthesis, bounded CEGIS and deterministic receipts.
- [x] Run focused tests; require GREEN.

### Task 3: Causal seed utility and invariance
**Files:**
- Modify: `tests/test_r258_active_probe.py`
- Modify: `cogcoder/r258_active_probe.py`

- [x] Add a full field-renaming metamorphic test and verify the R2.57 harness-free baseline fails under the same bounded setting.
- [x] Add full-target seed evaluation using existing `synthesize_with_vocabulary`, reject non-causal candidates, use canonical structural/profile search order and stop only after transformed challenge plus full original challenge prove causal utility.
- [x] Require focused GREEN and run R2.57 regressions.

### Task 4: Frozen authored benchmark and external harness
**Files:**
- Create: `benchmarks/kfigg/r258_active_probe_discovery.py`
- Create: `research/r258_external_active_probe_transfer.py`
- Create: `tests/test_r258_benchmark.py`

- [x] Write benchmark tests first: harness-free R2.57 baseline cannot solve within the frozen budget; R2.58 solves opaque episodes with zero false accepts and deterministic receipts.
- [x] Implement three distinct affine active-discovery worlds plus three transparent field-renaming metamorphic replays.
- [x] Implement external I/O-only transfer wrapper with no `_probe_rows` or manually named endpoint probe.
- [x] Require GREEN and deterministic byte-identical Phase-A recomputation.

### Task 5: CI, frozen evidence, World audit, delivery
**Files:**
- Create: `.github/workflows/r258-active-probe-discovery.yml`
- Create: `R2_58_PHASE_A_RESULT.json`
- Create: `research/R2_58_PRE_HOSTED_LOCK.json`
- Later release: `R2_58_DELIVERY.md`, `R2_57_TO_R2_58_EVOLUTION.md`, `R2_58_RELEASE_MANIFEST.json`, hosted verification and World evidence.

- [x] Freeze authored Phase-A output exactly and lock SHA-256 values before hosted evidence.
- [x] Run focused R2.58 tests and protected R2.57→R2.41 lineage locally in isolated Python processes.
- [x] Start a fresh Nolane World 0.8.0 living runtime and submit problem, unknown and local-evidence artifacts without claiming convergence.
- [ ] Commit all pre-hosted R2.58 capability files atomically to `r258-active-probe-discovery`.
- [ ] Use hosted CI for cross-Python and pinned external oracle evidence.
- [ ] Feed hosted evidence back into Nolane World, run audit/gate, preserve non-convergence if W5 does not pass, then freeze delivery and release bundle.
