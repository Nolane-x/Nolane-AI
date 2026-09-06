# External Core A5 Canonical Admission Firewall — Implementation Plan

**Goal:** Add a strict current/live admission lane for A2 manifest, authority-graph, handoff, and work-trace state while preserving all historical v1 serialization/restore behavior.

**Architecture:** `external.integration` owns a public secondary surface `integration_admission.py` under protocol `external-integration-admission-v2`. The new layer validates raw state types/shapes before any legacy v1 restore, binds restored subjects to an exact current admission context, and emits immutable/content-addressed admission wrappers/receipts/bundles. It never grants semantic authority.

**Version:** advance only `external.integration: 0.0.3 -> 0.0.4`. No global version and no dependency bump cascade.

**Spec:** `docs/superpowers/specs/2026-09-06-external-core-a5-canonical-admission-firewall-design.md`

## Global constraints

- Preserve existing v1 APIs and frozen historical evidence unchanged.
- No family H, governor, orchestrator, invoker, repair service, auto-migrator, Verification, Assurance, authorization, promotion, execution, release or deployment authority.
- Every semantic consumer validates receipt/wrapper integrity before use.
- Raw current admission performs no implicit `str`, `int`, `bool`, bytes decoding, or permissive collection conversion.
- Exact component-local version discipline must finish with zero findings.

---

## Task 1 — CI coverage and strict primitive RED

**Files**
- Modify `.github/workflows/external-core-a2.yml`
- Create `tests/test_external_core_a5_admission_primitives.py`
- Create `tests/test_external_core_a5_admission_adversarial.py`

**Steps**
1. Add A5 feature-push branch and `tests/test_external_core_a5_*.py` to the External Core workflow.
2. Write RED tests for exact string/bool/int/list/mapping validation, custom `__str__` laundering, duplicate rows, unknown/missing keys, and context content identity.
3. Open a draft PR if needed so the RED witness runs on GitHub Actions.
4. Confirm failures are capability failures because `integration_admission` is missing, not fixture errors.

## Task 2 — Admission context and receipt spine

**Files**
- Create `nolane/external_core/integration_admission.py`
- Extend Task 1 tests

**Interfaces**
- `CanonicalAdmissionContext.create/from_state/validate_integrity`
- `AdmissionDisposition`
- `AdmissionSubjectKind`
- `ProtocolAdmissionReceipt.create/from_state/validate_integrity`

**Steps**
1. Implement strict non-coercive primitives local to the owner surface.
2. Implement exact frontier canonicalization/digests and non-negative observation epoch.
3. Implement content-addressed admission receipt with exact owner/version/context binding.
4. GREEN focused primitive/adversarial tests.

## Task 3 — Manifest and authority-graph current admission

**Files**
- Modify `integration_admission.py`
- Create `tests/test_external_core_a5_manifest_graph_admission.py`

**Interfaces**
- `AdmittedManifest`
- `AdmittedAuthorityGraph`
- `admit_manifest_state`
- `admit_authority_graph_state`

**Steps**
1. RED: wrong-typed raw manifest fields that legacy v1 would stringify must fail before restore.
2. RED: self-consistent manifest/graph from another registry/profile must not admit.
3. Implement recursive strict raw schemas for manifest/edge/graph state.
4. Restore with existing v1 semantics only after strict validation.
5. Recheck exact current registry/profile identity and graph validation.
6. Add exact wrapper restore/integrity validation and direct-constructor forgery tests.

## Task 4 — Handoff current admission

**Files**
- Modify `integration_admission.py`
- Create `tests/test_external_core_a5_handoff_admission.py`

**Interfaces**
- `AdmittedHandoff`
- `admit_handoff_state`

**Steps**
1. RED custom-`__str__`, wrong list/row shape, enum-object, digest, and payload-state smuggling.
2. Strict-validate serialized handoff state before v1 restore.
3. Strict-validate current source/evidence/artifact/predecessor/freshness inputs.
4. Re-run A2 `validate_handoff_for_consumer` against exact current registry manifests.
5. Map A2 ACCEPTED/BLOCKED/UNKNOWN categorically into A5 disposition.
6. Bind exact current context and reject cross-context replay.

## Task 5 — Work-trace current admission

**Files**
- Modify `integration_admission.py`
- Create `tests/test_external_core_a5_trace_admission.py`

**Interfaces**
- `AdmittedWorkTrace`
- `admit_work_trace_state`

**Steps**
1. RED wrong-typed node/supersession state, forged IDs/digests, tuple-vs-list substitution and cross-handoff-frontier replay.
2. Strict-validate trace/node/supersession raw state before v1 restore.
3. Re-run predecessor/cycle/supersession/diagnostic checks.
4. Require referenced handoffs to exist in exact current handoff frontier.
5. Bind exact current context and wrapper identity.

## Task 6 — Canonical admission bundle, builder, and audit

**Files**
- Modify `integration_admission.py`
- Create `tests/test_external_core_a5_bundle.py`
- Create `tests/test_external_core_a5_canonical_audit.py`

**Interfaces**
- `CanonicalAdmissionBundle.create/from_state/validate_integrity`
- `build_canonical_admission_context`
- `build_canonical_admission_bundle`
- `run_canonical_admission_audit`
- module CLI `python -m nolane.external_core.integration_admission --check [--json]`

**Steps**
1. RED duplicate/rebound subject IDs and mixed-context child receipts.
2. Revalidate every child wrapper/receipt when bundling.
3. Enforce manifest/graph/handoff/trace cross-protocol population/reference invariants.
4. Build canonical current context without coercing source component constants.
5. Add read-only categorical audit with no mutation/repair path.

## Task 7 — Version/public contract/current docs closure

**Files**
- Modify `nolane/external_core/integration.py`
- Modify `nolane/external_core/__init__.py`
- Modify `nolane/metadata/component_versions.py`
- Modify `CURRENT/EXTERNAL_CORE.md`
- Update only current-state tests that explicitly project accepted component revisions
- Create `tests/test_external_core_a5_public_contract.py`

**Steps**
1. RED exact public contract expecting `external.integration==0.0.4`, A5 exports, CURRENT law, and only one revision delta.
2. Re-export structural/read-only A5 surfaces from Integration/package root.
3. Bump only `external.integration` revision `3 -> 4` and `COMPONENT_VERSION 0.0.3 -> 0.0.4`.
4. Update current accepted-version assertions only; do not touch frozen historical locks.
5. Update CURRENT with A5 law and non-authority semantics.
6. Run version discipline and debug ownership if any component other than Integration is requested.

## Task 8 — Exact verification and PR closure

**Steps**
1. Run full External Core workflow on exact head, Python 3.11 and 3.13.
2. Require External Core contracts GREEN, version discipline 0 findings, component projection GREEN, canonical A2+A3 audit GREEN, prior G/Assurance regressions GREEN, and A5 canonical admission audit GREEN.
3. Run Truth/Knowledge and full Refoundation on exact PR merge-ref for Python 3.11 and 3.13.
4. Classify frozen historical release-boundary failures without refreezing history.
5. Review diff for authority widening, auto-migration, hidden global version, extra component bumps, raw-v1 current bypass, and accidental v1 semantic changes.
6. Resolve PR review threads/blockers.
7. Verify exact merge-ref parents/tree/signature and record closure evidence.
8. Transition PR to Ready only when exact merge-ref acceptance is complete.
