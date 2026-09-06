# External Core A6 Temporal Re-attestation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a persisted A5 canonical admission bundle live-audit-clean only when the exact observation epoch is explicitly re-observed and matches the epoch bound into the bundle context.

**Architecture:** Keep all A5 admission-v2 serialized artifacts unchanged. Harden only the read-only audit path by adding an explicit `current_observed_epoch` proof, fail-closed unavailable/invalid/mismatch findings, audit protocol v2, and a component-local `external.integration` patch bump to 0.0.5.

**Tech Stack:** Python 3.11/3.13, dataclasses, pytest, GitHub Actions, canonical digest primitives already in `nolane.core.canonical_digest`.

**Spec:** `docs/superpowers/specs/2026-09-06-external-core-a6-temporal-reattestation-design.md`

## Global Constraints

- Scope is only `external.integration` hardening.
- Do not create family H, governor, orchestrator, invocation, Verification, Assurance, authorization, promotion, execution, repair, migration, deployment, or release authority.
- Preserve `external-integration-admission-v2` context/receipt/wrapper/bundle serialized state exactly.
- New audit protocol is `external-integration-admission-audit-v2`.
- `external.integration` advances only `0.0.4 -> 0.0.5`; no unrelated component revision changes.
- Frozen historical release witnesses remain unchanged.
- Persisted-bundle audit requires exact live epoch proof; `current >= admitted` is insufficient.

---

### Task 1: Prove the temporal replay gap with RED tests

**Files:**
- Create: `tests/test_external_core_a6_temporal_reattestation.py`

**Interfaces:**
- Consumes: `build_canonical_admission_bundle(observed_epoch: int, ...) -> CanonicalAdmissionBundle`
- Consumes: current `run_canonical_admission_audit(...) -> CanonicalAdmissionAuditReport`
- Produces: failing behavioral contract for `current_observed_epoch` and exact epoch re-attestation.

- [ ] **Step 1: Add RED tests for missing and drifted epoch proof**

```python
from __future__ import annotations

import pytest

from nolane.external_core.integration_admission_bundle import (
    build_canonical_admission_bundle,
    run_canonical_admission_audit,
)


def test_persisted_bundle_requires_live_observation_epoch() -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)
    report = run_canonical_admission_audit(bundle=bundle)
    assert {row.code for row in report.findings} == {"CURRENT_OBSERVATION_EPOCH_UNAVAILABLE"}


def test_persisted_bundle_rejects_later_epoch_even_when_other_state_is_unchanged() -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)
    report = run_canonical_admission_audit(bundle=bundle, current_observed_epoch=12)
    assert {row.code for row in report.findings} == {"OBSERVATION_EPOCH_CONTEXT_MISMATCH"}


def test_persisted_bundle_accepts_exact_live_epoch() -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)
    report = run_canonical_admission_audit(bundle=bundle, current_observed_epoch=11)
    assert report.findings == ()
```

- [ ] **Step 2: Add strict invalid-epoch adversarial cases**

```python
@pytest.mark.parametrize("value", [True, False, -1, 1.0, "11", b"11"])
def test_live_observation_epoch_rejects_noncanonical_values(value: object) -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=11)
    report = run_canonical_admission_audit(bundle=bundle, current_observed_epoch=value)  # type: ignore[arg-type]
    assert {row.code for row in report.findings} == {"CURRENT_OBSERVATION_EPOCH_INVALID"}
```

- [ ] **Step 3: Add fresh-builder compatibility contracts**

```python
def test_fresh_builder_uses_its_observed_epoch_as_live_proof() -> None:
    report = run_canonical_admission_audit(observed_epoch=11)
    assert report.findings == ()


def test_fresh_builder_reports_explicit_live_epoch_mismatch() -> None:
    report = run_canonical_admission_audit(observed_epoch=11, current_observed_epoch=12)
    assert {row.code for row in report.findings} == {"OBSERVATION_EPOCH_CONTEXT_MISMATCH"}
```

- [ ] **Step 4: Run the focused tests to prove RED**

Run: `pytest -q tests/test_external_core_a6_temporal_reattestation.py`

Expected on the pre-A6 implementation: calls using `current_observed_epoch` fail because the parameter does not exist, and the missing-live-epoch contract fails because the current persisted-bundle audit returns clean.

- [ ] **Step 5: Commit the RED test only**

```bash
git add tests/test_external_core_a6_temporal_reattestation.py
git commit -m "test: expose A6 temporal replay gap"
```

---

### Task 2: Implement exact live epoch re-attestation

**Files:**
- Modify: `nolane/external_core/integration_admission_bundle.py`
- Test: `tests/test_external_core_a6_temporal_reattestation.py`
- Test: `tests/test_external_core_a5_canonical_audit.py`

**Interfaces:**
- Consumes: `CanonicalAdmissionBundle.context.observed_epoch: int`
- Produces: `run_canonical_admission_audit(..., current_observed_epoch: int | None = None)`
- Produces findings `CURRENT_OBSERVATION_EPOCH_UNAVAILABLE`, `CURRENT_OBSERVATION_EPOCH_INVALID`, `OBSERVATION_EPOCH_CONTEXT_MISMATCH`.

- [ ] **Step 1: Add one strict helper for live epoch validation**

```python
def _live_observation_epoch(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("current observation epoch must be a non-negative integer")
    return value
```

- [ ] **Step 2: Extend the audit signature without changing admission-v2 artifacts**

Change the signature to:

```python
def run_canonical_admission_audit(
    *,
    bundle: CanonicalAdmissionBundle | None = None,
    observed_epoch: int = 0,
    current_observed_epoch: int | None = None,
    current_source_state_digests: Mapping[str, str] | None = None,
    current_evidence_digests: Mapping[str, str] | None = None,
    current_artifact_digests: Mapping[str, str] | None = None,
    current_freshness_fences: Mapping[str, str] | None = None,
    known_handoff_digests: Mapping[str, str] | None = None,
    current_work_trace_digests: Mapping[str, str] | None = None,
) -> CanonicalAdmissionAuditReport:
```

Capture `persisted_bundle = bundle is not None` before the builder branch.

- [ ] **Step 3: Resolve the effective live epoch deterministically**

After integrity/current-object validation and before registry/frontier findings:

```python
if persisted_bundle and current_observed_epoch is None:
    findings.append(
        AdmissionAuditFinding(
            code="CURRENT_OBSERVATION_EPOCH_UNAVAILABLE",
            detail="admission context observation epoch was not re-observed for the live audit",
            subject_id="canonical-admission-bundle",
        )
    )
else:
    raw_live_epoch = observed_epoch if current_observed_epoch is None else current_observed_epoch
    try:
        live_epoch = _live_observation_epoch(raw_live_epoch)
    except ValueError as exc:
        findings.append(
            AdmissionAuditFinding(
                code="CURRENT_OBSERVATION_EPOCH_INVALID",
                detail=str(exc),
                subject_id="canonical-admission-bundle",
            )
        )
    else:
        if live_epoch != bundle.context.observed_epoch:
            findings.append(
                AdmissionAuditFinding(
                    code="OBSERVATION_EPOCH_CONTEXT_MISMATCH",
                    detail="admission context observation epoch does not match the live re-observation",
                    subject_id="canonical-admission-bundle",
                )
            )
        )
```

Do not suppress registry/frontier/re-admission findings when temporal findings exist.

- [ ] **Step 4: Update existing A5 clean persisted-bundle tests to provide exact live epoch**

In `tests/test_external_core_a5_canonical_audit.py`, every test whose intent is unrelated to missing temporal proof and which expects a clean or isolated non-temporal finding must pass `current_observed_epoch=11` for bundles created with epoch 11. Do not change the expected A5 finding codes.

- [ ] **Step 5: Run focused A6 + A5 audit tests**

Run: `pytest -q tests/test_external_core_a6_temporal_reattestation.py tests/test_external_core_a5_canonical_audit.py`

Expected: PASS.

- [ ] **Step 6: Commit the minimal semantic implementation**

```bash
git add nolane/external_core/integration_admission_bundle.py tests/test_external_core_a5_canonical_audit.py tests/test_external_core_a6_temporal_reattestation.py
git commit -m "feat: require A6 live epoch re-attestation"
```

---

### Task 3: Advance the audit/component version surface exactly once

**Files:**
- Modify: `nolane/external_core/integration.py`
- Modify: `nolane/external_core/integration_admission.py`
- Modify: `nolane/external_core/integration_admission_bundle.py`
- Modify: `nolane/external_core/compatibility.py`
- Modify: `nolane/metadata/component_versions.py`
- Modify/Test: `tests/test_external_core_a5_public_contract.py`
- Modify/Test: `tests/test_external_core_integration_evolution_public_contract.py`
- Modify/Test: `tests/test_refoundation_component_versions.py`
- Modify/Test: any exact version-projection tests identified by the External Core CI failure output.

**Interfaces:**
- Produces canonical component version `external.integration == 0.0.5`.
- Produces audit protocol `external-integration-admission-audit-v2`.
- Preserves admission protocol `external-integration-admission-v2`.

- [ ] **Step 1: Change only the integration-owned version constants**

Set:

```python
# nolane/external_core/integration.py
COMPONENT_VERSION = "0.0.5"

# nolane/external_core/integration_admission.py
COMPONENT_VERSION = "0.0.5"

# nolane/external_core/integration_admission_bundle.py
COMPONENT_VERSION = "0.0.5"
ADMISSION_AUDIT_PROTOCOL = "external-integration-admission-audit-v2"

# nolane/external_core/compatibility.py
SEMANTIC_SURFACE_VERSION = "0.0.5"
```

Leave `ADMISSION_PROTOCOL = "external-integration-admission-v2"` and `ADMISSION_BUNDLE_PROTOCOL = "external-integration-admission-bundle-v2"` unchanged.

- [ ] **Step 2: Advance only the component-local revision table**

Change exactly:

```python
"external.integration": 5,
```

No other entry in `_COMPONENT_REVISIONS` changes.

- [ ] **Step 3: Update public-contract assertions to 0.0.5 / audit-v2**

Replace only expectations that intentionally project the current `external.integration` version or current audit protocol. Do not rewrite historical serialized fixture expectations for admission-v2 artifacts.

- [ ] **Step 4: Run version/public-contract tests**

Run:

```bash
pytest -q \
  tests/test_external_core_a5_public_contract.py \
  tests/test_external_core_integration_evolution_public_contract.py \
  tests/test_refoundation_component_versions.py \
  tests/test_external_core_a6_temporal_reattestation.py
```

Expected: PASS.

- [ ] **Step 5: Commit the version/protocol projection**

```bash
git add nolane/external_core/integration.py nolane/external_core/integration_admission.py nolane/external_core/integration_admission_bundle.py nolane/external_core/compatibility.py nolane/metadata/component_versions.py tests
git commit -m "chore: advance external integration for A6 audit v2"
```

---

### Task 4: Close regressions, docs, CI evidence, and PR

**Files:**
- Modify: `CURRENT/EXTERNAL_CORE.md`
- Modify: `.github/workflows/external-core-a2.yml` only if the existing A5 test glob/list does not naturally include the new A6 test file.
- Existing tests/workflows as verification surfaces.

**Interfaces:**
- Produces documented A6 currentness invariant and exact acceptance evidence.

- [ ] **Step 1: Run the complete External Core contract set locally or on GitHub Actions**

Run the exact command used by `.github/workflows/external-core-a2.yml` for External Core contracts, then version discipline, canonical projection, A2/A3 coherence audit, A6 admission audit, and prior G/Assurance regressions.

Expected: Python 3.11 and 3.13 success, zero version-discipline findings, clean canonical A2/A3 audit, clean A6 audit.

- [ ] **Step 2: Update `CURRENT/EXTERNAL_CORE.md`**

Add a concise A6 section stating:

- persisted admission snapshots are epoch-bound;
- live audit requires exact epoch re-observation;
- missing epoch proof fails closed;
- later/earlier epochs are mismatch, not freshness proof;
- currentness remains descriptive and grants no authority;
- admission-v2 serialized state remains backward-compatible.

- [ ] **Step 3: Commit docs/CI-only closure changes**

```bash
git add CURRENT/EXTERNAL_CORE.md .github/workflows/external-core-a2.yml
git commit -m "docs: record A6 temporal re-attestation boundary"
```

If the workflow needs no edit, commit only `CURRENT/EXTERNAL_CORE.md`.

- [ ] **Step 4: Open a PR against exact current `main`**

PR title: `A6: temporal re-attestation for canonical admission`

PR body must record the RED head/run, GREEN exact-head runs, component-local version change, preserved admission-v2 compatibility, and explicit non-authority boundaries.

- [ ] **Step 5: Verify the synthetic merge-ref before merge**

Require the merge-ref parents to be exactly the current base SHA plus the exact feature head. Run/confirm External Core 3.11+3.13, Refoundation Epoch 0, Truth/Knowledge coverage, Memory Learning Substrate, E Acting Transactional Runtime, R1.9, R2.0i, and the applicable full-repository release bundle gates. Classify frozen historical-boundary failures without rewriting them.

- [ ] **Step 6: Merge only with an expected-head guard after the user's standing merge permission remains applicable**

Use merge method `merge`, with `expected_head_sha=<verified feature head>`. After merge, verify `main` points to the returned merge SHA and that its tree equals the verified synthetic merge-ref tree.
