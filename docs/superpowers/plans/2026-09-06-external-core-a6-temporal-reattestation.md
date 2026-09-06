# External Core A6 Temporal Re-attestation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make a persisted A5 canonical admission bundle live-audit-clean only when the exact observation epoch is explicitly re-observed and matches the epoch bound into the bundle context.

**Architecture:** Preserve all A5 admission-v2 serialized artifacts and receipt identities. Harden only the read-only audit qualification path with explicit `current_observed_epoch`, categorical unavailable/invalid/mismatch findings, audit protocol v2, and the current canonical `external.integration` revision 0.0.5. The unchanged admission-v2 artifact issuer remains frozen at owner version 0.0.4 because that value participates in receipt identity and restore validation.

**Spec:** `docs/superpowers/specs/2026-09-06-external-core-a6-temporal-reattestation-design.md`

## Global constraints

- Scope is only `external.integration` hardening.
- Do not create family H, governor, orchestrator, invocation, Verification, Assurance, authorization, promotion, execution, repair, migration, deployment, or release authority.
- Preserve `external-integration-admission-v2` context/receipt/wrapper and `external-integration-admission-bundle-v2` serialized state exactly.
- Preserve `integration_admission.COMPONENT_VERSION == "0.0.4"`; A5 receipt owner version is historical artifact identity, not the current canonical component revision.
- New audit protocol is `external-integration-admission-audit-v2` with `admission-audit-v2-*` report digests.
- Current canonical `external.integration` advances only `0.0.4 -> 0.0.5`; no unrelated component revision changes.
- Frozen historical release witnesses remain unchanged.
- Persisted-bundle audit requires exact live epoch proof; `current >= admitted` is insufficient.

---

### Task 1: Prove temporal replay with RED tests — COMPLETE

**File:** `tests/test_external_core_a6_temporal_reattestation.py`

Evidence:

- [x] Missing live epoch RED: head `25e4c730187c035a678ca147370cec764721da0b`, 267 passed / 1 failed.
- [x] Earlier/later live epoch RED: head `c4b4056d23f7e83129bee7fd78c5b2a0831b0ad4`, 269 passed / 2 failed.
- [x] Strict-type RED: head `c9602506e559a02ab52f426d9521690bc9cc7fdb`, 271 passed / 6 failed.
- [x] Exact epoch equality contract passes.
- [x] Fresh-builder compatibility contract added.

---

### Task 2: Implement exact live epoch re-attestation — COMPLETE

**Files:**
- `nolane/external_core/integration_admission_bundle.py`
- `tests/test_external_core_a6_temporal_reattestation.py`
- `tests/test_external_core_a5_canonical_audit.py`

- [x] Add strict `_live_observation_epoch`: only exact non-negative `int`; `bool` rejected.
- [x] Add keyword-only `current_observed_epoch`.
- [x] Persisted bundle + missing proof => `CURRENT_OBSERVATION_EPOCH_UNAVAILABLE`.
- [x] Invalid proof => `CURRENT_OBSERVATION_EPOCH_INVALID`.
- [x] Valid but non-equal proof => `OBSERVATION_EPOCH_CONTEXT_MISMATCH`.
- [x] Fresh builder reuses its own `observed_epoch` as live proof.
- [x] Existing A5 registry/frontier/readmission tests now supply exact epoch where temporal proof is not their target.
- [x] GREEN behavior head `9d04aa612db6474e4dc5f3f4de833b9573373076`: 277 External Core contracts pass on Python 3.11 and 3.13; only expected version-discipline finding remained.

---

### Task 3: Advance the current audit/component surface without rewriting A5 receipts — IN PROGRESS

**Current-lane files:**
- `nolane/external_core/integration.py`
- `nolane/external_core/integration_admission_bundle.py`
- `nolane/external_core/compatibility.py`
- `nolane/metadata/component_versions.py`

**Frozen artifact file:**
- `nolane/external_core/integration_admission.py`

- [x] Set `integration.COMPONENT_VERSION = "0.0.5"`.
- [x] Set `compatibility.SEMANTIC_SURFACE_VERSION = "0.0.5"`.
- [x] Set `integration_admission_bundle.COMPONENT_VERSION = "0.0.5"`.
- [x] Set `ADMISSION_AUDIT_PROTOCOL = "external-integration-admission-audit-v2"` and report digest prefix to `admission-audit-v2-`.
- [x] Advance only `_COMPONENT_REVISIONS["external.integration"]` from 4 to 5.
- [x] Keep `integration_admission.COMPONENT_VERSION = "0.0.4"` and `ADMISSION_PROTOCOL = "external-integration-admission-v2"` so existing A5 receipt owner identity remains restorable.
- [x] Keep `ADMISSION_BUNDLE_PROTOCOL = "external-integration-admission-bundle-v2"`.
- [x] Update A6/A5/current integration public contracts and canonical component-version expectations.
- [ ] Run latest exact-head External Core matrix and remove any remaining stale projections without touching frozen A5 artifact expectations.

---

### Task 4: Close docs, CI, exact acceptance and integration — IN PROGRESS

**Files:**
- `CURRENT/EXTERNAL_CORE.md`
- `.github/workflows/external-core-a2.yml`
- A6 spec/plan and PR evidence.

- [x] Add branch and `tests/test_external_core_a6_*.py` to External Core CI.
- [ ] Rename current audit gate from A5 to A6 in CI output/path without altering semantics.
- [ ] Update `CURRENT/EXTERNAL_CORE.md` with the epoch-bound currentness invariant and frozen A5 receipt compatibility.
- [ ] Run exact-head External Core Python 3.11 + 3.13: contracts, zero version-discipline findings, canonical projection, A2/A3 audit, A6 audit, prior G/Assurance regressions.
- [ ] Open PR `A6: temporal re-attestation for canonical admission` against exact current `main` and record RED/GREEN evidence.
- [ ] Verify synthetic merge-ref parents are exactly current base + exact feature head.
- [ ] Confirm broader Refoundation Epoch 0, Truth/Knowledge, Memory, E Acting, R1.9, R2.0i and applicable full-repository gates on that exact merge-ref; classify frozen historical release-boundary failures without rewriting them.
- [ ] Inspect review surface and race guards immediately before integration.
- [ ] Merge with method `merge` and `expected_head_sha=<verified feature head>` under the user's standing merge permission.
- [ ] Verify post-merge `main`, merge parents, tree equality with verified synthetic merge-ref, and GitHub signature.

## Completion criterion

A6 is complete only when a persisted bundle cannot pass current/live audit without exact epoch re-observation; invalid epoch representations never coerce; existing A5 admission-v2 receipts remain byte/identity restorable at owner version 0.0.4; the current canonical integration/audit lane is revision 0.0.5/audit-v2; all substantive exact-head and exact-merge-ref gates are green; and no authority boundary widens.