# External Core Scoped Evidence Revalidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add strict scoped evidence v2 and exact-context integration revalidation v2 so evidence cannot be replayed or laundered across component/version transitions.

**Architecture:** Preserve all v1 evidence/revalidation state for backward compatibility. Add a separate content-addressed `ScopedEvidenceRecord` protocol in `external.evidence`, then add exact transition scope, deterministic challenges, scope-bound evidence bindings, scoped assessment and completion receipt in `external.integration`. Only `external.evidence` and `external.integration` revisions advance by one.

**Tech Stack:** Python 3.11/3.13, frozen dataclasses, enums, canonical JSON/digest utilities, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-05-external-core-scoped-evidence-revalidation-design.md`

## Global Constraints

- No global External Core version.
- Advance exactly `external.evidence: 0.0.1 -> 0.0.2` and `external.integration: 0.0.2 -> 0.0.3`.
- Keep legacy `EvidenceRecord` and v1 integration revalidation backward-compatible.
- No family H, central governor, orchestrator, invocation, Verification, Assurance, authorization, promotion, execution, deploy, repair, auto-migration or runtime-registration authority.
- All new semantic state is immutable/content-addressed and exact-restorable.
- Direct-constructor forged state must fail at semantic consumers.
- Historical frozen release artifacts remain untouched.

---

### Task 1: Scoped Evidence v2 Contract

**Files:**
- Modify: `nolane/external_core/evidence.py`
- Create: `tests/test_external_core_scoped_evidence.py`
- Create: `tests/test_external_core_scoped_evidence_adversarial.py`

**Interfaces:**
- Produces: `ScopedEvidenceRecord.create(...)`, `ScopedEvidenceRecord.from_state(...)`, `ScopedEvidenceRecord.validate_integrity()`.

- [ ] **Step 1: Write failing tests** for strict identity fields, exact bool/int semantics, canonical ordering, exact restore, digest tampering, direct-constructor forgery, stale/future epoch helper checks, and v1 compatibility.
- [ ] **Step 2: Run External Core contract workflow and verify RED** because `ScopedEvidenceRecord` is missing.
- [ ] **Step 3: Implement `ScopedEvidenceRecord`** under protocol `scoped-evidence-v2`; preserve `EvidenceRecord` unchanged.
- [ ] **Step 4: Run focused tests and verify GREEN**.
- [ ] **Step 5: Commit** scoped evidence implementation.

### Task 2: Exact Revalidation Scope and Challenge Derivation

**Files:**
- Create: `nolane/external_core/integration_scoped_revalidation.py`
- Create: `tests/test_external_core_integration_scoped_revalidation.py`

**Interfaces:**
- Consumes: `ComponentEvolutionDelta`, `IntegrationImpactClosure`, `RevalidationPlan`, `ExternalAuthorityGraph`.
- Produces: `RevalidationScope`, `RevalidationChallenge`, `build_revalidation_scope(...)`, `build_revalidation_challenges(...)`, `challenge_subject_digest(...)`.

- [ ] **Step 1: Write failing tests** proving scope binds delta/old-new manifests/plan/closure/graph and challenge derivation is deterministic for each exact requirement.
- [ ] **Step 2: Verify RED** because v2 integration module is missing.
- [ ] **Step 3: Implement strict scope/challenge content identities**, graph-manifest target-version binding, exact restore and integrity validation.
- [ ] **Step 4: Verify GREEN** including downstream impacted component target versions.
- [ ] **Step 5: Commit** scope/challenge implementation.

### Task 3: Scope-Bound Evidence Binding and Assessment

**Files:**
- Modify: `nolane/external_core/integration_scoped_revalidation.py`
- Modify: `tests/test_external_core_integration_scoped_revalidation.py`
- Create: `tests/test_external_core_integration_scoped_revalidation_adversarial.py`

**Interfaces:**
- Consumes: `ScopedEvidenceRecord`, `RevalidationScope`, `RevalidationChallenge`.
- Produces: `ScopedRevalidationEvidenceBinding`, `ScopedRevalidationAssessment`, `assess_scoped_revalidation(...)`.

- [ ] **Step 1: Write RED adversarial tests** for cross-version replay, cross-delta replay, cross-plan replay, graph substitution, challenge substitution, wrong subject/scope digest, duplicate binding, self-certification, stale observation, v1 evidence rejection and direct-constructor forgeries.
- [ ] **Step 2: Run and confirm failures are capability failures, not fixture errors**.
- [ ] **Step 3: Implement binding admission and categorical assessment** with exact challenge coverage and optional `minimum_observed_epoch` freshness fence.
- [ ] **Step 4: Run focused and full External Core contracts; verify GREEN**.
- [ ] **Step 5: Commit** binding/assessment implementation.

### Task 4: Revalidation Completion Receipt

**Files:**
- Modify: `nolane/external_core/integration_scoped_revalidation.py`
- Modify: `tests/test_external_core_integration_scoped_revalidation.py`
- Modify: `tests/test_external_core_integration_scoped_revalidation_adversarial.py`

**Interfaces:**
- Produces: `RevalidationCompletionReceipt.create(...)`, exact restore/integrity validation.

- [ ] **Step 1: Write RED tests** showing non-CURRENT assessment cannot mint completion and forged completion state is rejected.
- [ ] **Step 2: Implement minimal immutable completion receipt** bound to exact scope/plan/assessment/challenge/binding IDs.
- [ ] **Step 3: Verify GREEN** and assert completion exposes no authority/control methods.
- [ ] **Step 4: Commit** completion receipt.

### Task 5: Component-Local Version Advances and Public Contract

**Files:**
- Modify: `nolane/external_core/evidence.py`
- Modify: `nolane/external_core/integration.py`
- Modify: `nolane/external_core/compatibility.py` if it carries the integration component semantic version surface
- Modify: `nolane/metadata/component_versions.py`
- Modify: `nolane/external_core/__init__.py`
- Modify: `CURRENT/EXTERNAL_CORE.md`
- Modify: current-state tests that explicitly assert evidence/integration versions
- Create or modify: `tests/test_external_core_scoped_revalidation_public_contract.py`

**Interfaces:**
- Public safe exports: scoped evidence/revalidation immutable types and pure builders/assessor only.

- [ ] **Step 1: Write RED public/version tests** requiring exactly evidence 0.0.2 and integration 0.0.3, no unrelated revision change, safe package exports and CURRENT authority text.
- [ ] **Step 2: Advance semantic version constants and canonical revision map exactly once for the two owners**.
- [ ] **Step 3: Export only authority-neutral v2 surfaces** and update CURRENT docs.
- [ ] **Step 4: Run component-local version discipline against base `6b6cc2ca991d4a0f33605911c563553e626f3f21`; require `PASS (0 finding(s))`**.
- [ ] **Step 5: Commit** version/public-contract changes.

### Task 6: Workflow Coverage and Adversarial Inclusion

**Files:**
- Modify: `.github/workflows/external-core-a2.yml` only if existing globs do not already include the new test filenames.
- Modify: relevant test glob coverage assertions if present.

**Interfaces:**
- CI must execute all new scoped-evidence and scoped-revalidation tests on Python 3.11 and 3.13.

- [ ] **Step 1: Prove new tests are actually included by the workflow**; add a RED coverage assertion if any filename escapes the glob.
- [ ] **Step 2: Fix workflow glob minimally if required**.
- [ ] **Step 3: Run exact-head External Core CI on both Python versions**.
- [ ] **Step 4: Require contracts, version discipline, projection, canonical audit and prior G/Assurance regressions all green**.
- [ ] **Step 5: Commit** workflow coverage change only if needed.

### Task 7: Exact-Head Review and PR Closure

**Files:**
- No production changes unless review finds a real defect.

**Interfaces:**
- Produces exact-head and exact PR merge-tree acceptance evidence.

- [ ] **Step 1: Compare branch to `main`** and confirm only intended files/components changed; explicitly inspect revision map delta.
- [ ] **Step 2: Run exact-head External Core workflow on Python 3.11/3.13 and capture counts**.
- [ ] **Step 3: Open draft PR** from `upgrade/external-core-scoped-evidence-revalidation` to `main`.
- [ ] **Step 4: Run/observe exact PR merge-ref External Core and Refoundation Epoch 0 substantive gates on Python 3.11/3.13**.
- [ ] **Step 5: Classify frozen historical release-boundary reds without modifying frozen artifacts**.
- [ ] **Step 6: Scan submitted reviews and inline review threads**; fix real blockers with fresh exact-head verification.
- [ ] **Step 7: Update PR body with exact head/base/merge-ref, version-map delta and quantitative CI evidence, then mark Ready**.
- [ ] **Step 8: Do not merge without explicit user permission; if permission is given, merge with `expected_head_sha`, verify official tree equals tested merge-ref tree, confirm `main`, run post-merge integrity gates and add closure witness.**
