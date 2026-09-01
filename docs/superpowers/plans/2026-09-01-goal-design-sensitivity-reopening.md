# Goal/Design Sensitivity-Driven Reopening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace coarse assumption-change invalidation with deterministic sensitivity-driven reopening authority and structured proof-obligation lifecycle while preserving historical Goal/Design receipt semantics.

**Architecture:** Add a parallel, content-addressed `DecisionReopeningAuthority` that captures per-decision truth baselines at admission, evaluates materiality of later assumption changes, and owns structured reopening cases/obligations. Existing `DecisionLifecycle.STALE` remains the compatibility projection only for materially reopened decisions; low-materiality drift remains ACTIVE but is explicitly reviewed. The truth-maintenance system remains the source of assumption status and does not delegate truth authority to the reopening layer.

**Tech Stack:** Python 3.11/3.12, dataclasses, enums, deterministic `stable_digest`, pytest, GitHub Actions.

**Spec:** `docs/GOAL_DESIGN_TRUTH_MAINTENANCE.md`

## Global Constraints

- Preserve v1/v2/v3 decision receipt identities byte-for-byte.
- Do not mutate Requirements, Planning, Architecture, Integration, Context, or Family-A truth ownership.
- Direct REFUTED bound assumptions always require reopening.
- Reopening sensitivity must include assumption criticality, truth-state transition magnitude, decision class, and unresolved uncertainty pressure.
- Low-materiality supported drift must not blindly stale an otherwise active decision.
- Satisfying reopening proof obligations never reactivates an old receipt when the bound truth snapshot changed; readmission must mint new authority.
- Reopening state must be deterministic, content-addressed, persistable, and fail closed on tamper/rebind.
- All production changes require a previously observed RED test and hosted Goal Design acceptance on Python 3.11 and 3.12.

---

### Task 1: First-Class Reopening Authority

**Files:**
- Create: `nolane/external_core/goal_design_reopening.py`
- Test: `tests/test_goal_design_sensitivity_reopening.py`

**Interfaces:**
- Consumes: `AssumptionTruthMaintenance`, `AssumptionAssessment`, `AssumptionStatus`, `DecisionClass`, `UncertaintyItem`, `stable_digest`.
- Produces: `DecisionReopeningAuthority`, `DecisionReopeningBaseline`, `ReopeningAssessment`, `ReopeningCase`, `ReopeningObligation`, and their enums.

- [x] **Step 1: Write the failing tests**

The committed RED suite requires: low-materiality monitoring, unconditional REFUTED reopening, irreversible/uncertainty sensitivity, evidence-bearing obligation resolution, new-receipt requirement, persistence, and tamper detection.

- [x] **Step 2: Run tests and verify RED**

Hosted Goal Design run `33468475056`, Python 3.11 job `99733156038`, fails during collection with `ModuleNotFoundError: nolane.external_core.goal_design_reopening`.

- [ ] **Step 3: Implement deterministic baseline/materiality/case/obligation authority**

Use exact per-assumption admission baselines. Compute materiality only for bound assumptions in the affected closure. REFUTED always material; otherwise score state transition and evidence-score deltas weighted by criticality and unresolved uncertainty pressure, with stricter thresholds as reversibility decreases.

- [ ] **Step 4: Verify focused tests GREEN**

Run: `python -m pytest -q tests/test_goal_design_sensitivity_reopening.py`
Expected: all reopening tests pass.

### Task 2: Runtime Integration

**Files:**
- Modify: `nolane/external_core/goal_design_runtime.py`
- Test: `tests/test_goal_design_sensitivity_reopening.py`
- Regression: `tests/test_goal_design_truth_runtime.py`

**Interfaces:**
- Consumes: `DecisionReopeningAuthority.assess_change()` and `register_decision()`.
- Produces: sensitivity-aware `AssumptionRuntimeImpact.reviewed_decision_ids` and `reopening_case_ids`.

- [ ] **Step 1: Register truth-bound decision baselines at admission**

Bind selected decision class, exact assumption refs, exact truth snapshot, and unresolved uncertainty pressure without changing receipt identity.

- [ ] **Step 2: Replace blind assumption invalidation with reopening assessment**

Always record reviewed decisions. Only `REOPEN_REQUIRED` transitions to `STALE` and gets an invalidation authority event; `NO_REOPEN` remains ACTIVE.

- [ ] **Step 3: Make revalidation use the same policy**

A changed truth digest with a registered reopening baseline is evaluated by the reopening authority instead of being blindly invalidated. Missing baseline remains conservative/fail-closed for historical restored state.

- [ ] **Step 4: Run complete Goal/Design suite**

Run: `python -m pytest -q tests/test_goal_design*.py`
Expected: all historical and new Goal/Design tests pass.

### Task 3: Persistence and Adversarial Hardening

**Files:**
- Modify: `tests/test_goal_design_sensitivity_reopening.py`
- Modify if required: `nolane/external_core/goal_design_reopening.py`

**Interfaces:**
- Consumes: `DecisionReopeningAuthority.to_state/from_state`.
- Produces: deterministic schema-v1 reopening state with row/state digests and identity-rebind rejection.

- [ ] **Step 1: Verify roundtrip equivalence and tamper rejection**

Mutating case sensitivity or baseline/obligation identities must fail restore with digest/identity error.

- [ ] **Step 2: Verify duplicate registration is idempotent only for identical authority content**

Same receipt/body returns the existing baseline; different decision class/truth snapshot/assumption set fails closed.

- [ ] **Step 3: Verify obligation evidence is immutable after satisfaction**

A satisfied obligation cannot be rebound to different evidence.

### Task 4: Hosted Acceptance and Integration Race Guard

**Files:**
- No production file changes unless a genuine regression is discovered.

**Interfaces:**
- Produces: exact-head hosted acceptance evidence and safe merge candidate.

- [ ] **Step 1: Run Goal Design Coherence Plane on Python 3.11 and 3.12**
- [ ] **Step 2: Run Refoundation and applicable integrity gates**
- [ ] **Step 3: Race-guard current `main`**
- [ ] **Step 4: If main moved without D overlap, rebuild exact union and rerun evidence**
- [ ] **Step 5: Merge with expected-head protection only after exact-head GREEN**
- [ ] **Step 6: Verify actual-main push Goal Design/integrity workflows before declaring CLOSED/GREEN**
