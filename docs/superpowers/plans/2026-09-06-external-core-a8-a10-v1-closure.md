# External Core A8–A10 v1 Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the common External Core architectural generation at A10 by adding complete-surface observation, provenance-bound observation receipts, and caller-evidence-driven continuity/fork validation while preserving every frozen A5–A7 artifact identity.

**Architecture:** Add one focused `nolane.external_core.observation` module containing the final reusable observation model. A8, A9 and A10 are separate TDD milestones against that one model, then `integration_admission_bundle.py` consumes the observation envelope in the current audit lane. Frozen admission-v2 and bundle-v2 remain byte-semantically unchanged; the final current lane advances once to `external.integration 0.0.7` and audit-v4.

**Tech Stack:** Python 3.11/3.13, dataclasses, canonical JSON/digest helpers, pytest, GitHub Actions, existing External Core registry/profile/admission contracts.

**Spec:** `docs/superpowers/specs/2026-09-06-external-core-a8-a10-v1-closure-design.md`

## Global Constraints

- Scope is External Core common boundary only.
- Stop architectural evolution at A10 and declare External Core v1 architecture complete only after verified production merge.
- `nolane.external_core.integration_admission.COMPONENT_VERSION` remains exactly `0.0.4`.
- `ADMISSION_PROTOCOL` remains exactly `external-integration-admission-v2`.
- `ADMISSION_BUNDLE_PROTOCOL` remains exactly `external-integration-admission-bundle-v2`.
- Historical A2–A7 states and frozen release witnesses are not rewritten or refrozen.
- External Core remains read-only/descriptive: no execution, authorization, promotion, learning, deployment, repair, migration, runtime registration, stateful chain-head ownership, family H, or central governor.
- A6 exact same-observation epoch equality remains unchanged.
- A7 single-snapshot semantics remain unchanged and are the capture substrate for A8–A10.
- Final current lane target: `external.integration 0.0.7`, compatibility surface `0.0.7`, metadata revision `7`, audit-v4, observation-v1.
- All new parsers are strict before coercion and fail closed on malformed raw state.

## File Structure

- Create `nolane/external_core/observation.py` for surface contracts, receipts, envelopes, strict restore, completeness/provenance checks, transition checks, and fork detection.
- Modify `nolane/external_core/integration_admission_bundle.py` for one capture path and current v4 audit integration.
- Modify `nolane/external_core/integration.py`, `nolane/external_core/compatibility.py`, and `nolane/metadata/component_versions.py` only for final current-lane projection.
- Modify `.github/workflows/external-core-a2.yml` and `CURRENT/EXTERNAL_CORE.md` for final CI coverage and architecture seal.
- Create `tests/test_external_core_a8_observation_completeness.py`.
- Create `tests/test_external_core_a9_observation_provenance.py`.
- Create `tests/test_external_core_a10_observation_continuity.py`.
- Update only tests that intentionally project the current `external.integration` version.

---

### Task 1: A8 RED — prove completeness is absent after A7

**Files:**
- Create: `tests/test_external_core_a8_observation_completeness.py`

**Interfaces:**
- Consumes current canonical registry/profile and frontier digest helpers.
- Produces failing A8 expectations before `observation.py` exists.

- [ ] **Step 1: Write exact imports and fixtures**

```python
from __future__ import annotations

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.audit import build_canonical_registry
from nolane.external_core.integration_admission import canonical_frontier_digest
from nolane.external_core.observation import (
    CanonicalObservationEnvelope,
    CanonicalObservationSurfaceContract,
    REQUIRED_SURFACE_KINDS,
    SurfaceObservationReceipt,
    validate_observation_completeness,
)


def _component_ids() -> tuple[str, ...]:
    registry = build_canonical_registry()
    return tuple(row.component_id for row in registry.manifests)


def _surface_digests() -> dict[str, str]:
    return {
        "registry": "registry-state-1",
        "authority-graph": "authority-state-1",
        "source-state": canonical_frontier_digest("source-state", {}),
        "evidence": canonical_frontier_digest("evidence", {}),
        "artifact": canonical_frontier_digest("artifact", {}),
        "freshness": canonical_frontier_digest("freshness", {}),
        "handoff": canonical_frontier_digest("handoff", {}),
        "work-trace": canonical_frontier_digest("work-trace", {}),
    }


def _receipt(kind: str, state_digest: str, *, complete: bool = True, epoch: int = 7) -> SurfaceObservationReceipt:
    return SurfaceObservationReceipt.create(
        surface_kind=kind,
        provider_id=f"provider:{kind}",
        provider_version="1",
        source_locator=f"tests:{kind}",
        scope_digest=canonical_digest({"surface_kind": kind, "scope": "complete"}),
        observed_state_digest=state_digest,
        enumeration_complete=complete,
        observed_epoch=epoch,
    )


def _envelope(receipts: tuple[SurfaceObservationReceipt, ...], *, epoch: int = 7) -> CanonicalObservationEnvelope:
    digests = _surface_digests()
    return CanonicalObservationEnvelope.create(
        surface_contract=CanonicalObservationSurfaceContract.create(required_component_ids=_component_ids()),
        observed_epoch=epoch,
        registry_digest=digests["registry"],
        authority_graph_digest=digests["authority-graph"],
        source_state_frontier_digest=digests["source-state"],
        evidence_frontier_digest=digests["evidence"],
        artifact_frontier_digest=digests["artifact"],
        freshness_fence_frontier_digest=digests["freshness"],
        handoff_frontier_digest=digests["handoff"],
        work_trace_frontier_digest=digests["work-trace"],
        surface_receipts=receipts,
        chain_id="external-core:default",
        previous_observation_digest=None,
    )
```

- [ ] **Step 2: Add exact RED cases**

```python
def test_required_surface_kinds_are_exact_and_closed() -> None:
    assert REQUIRED_SURFACE_KINDS == (
        "artifact",
        "authority-graph",
        "evidence",
        "freshness",
        "handoff",
        "registry",
        "source-state",
        "work-trace",
    )


def test_contract_rejects_duplicate_component_identity() -> None:
    with pytest.raises(ValueError, match="duplicate required component identity"):
        CanonicalObservationSurfaceContract.create(required_component_ids=("external.a", "external.a"))


def test_receipt_rejects_bool_epoch() -> None:
    with pytest.raises(ValueError, match="exact non-negative integer"):
        SurfaceObservationReceipt.create(
            surface_kind="source-state",
            provider_id="provider:source",
            provider_version="1",
            source_locator="tests:source",
            scope_digest="scope-1",
            observed_state_digest="state-1",
            enumeration_complete=True,
            observed_epoch=True,
        )


def test_missing_required_surface_is_reported() -> None:
    digests = _surface_digests()
    receipts = tuple(_receipt(kind, digest) for kind, digest in digests.items() if kind != "artifact")
    findings = validate_observation_completeness(
        _envelope(receipts),
        expected_component_ids=_component_ids(),
        observed_surface_digests=digests,
    )
    assert "OBSERVATION_REQUIRED_SURFACE_MISSING" in {row.code for row in findings}


def test_incomplete_enumeration_is_reported() -> None:
    digests = _surface_digests()
    receipts = tuple(_receipt(kind, digest, complete=(kind != "source-state")) for kind, digest in digests.items())
    findings = validate_observation_completeness(
        _envelope(receipts),
        expected_component_ids=_component_ids(),
        observed_surface_digests=digests,
    )
    assert "OBSERVATION_ENUMERATION_INCOMPLETE" in {row.code for row in findings}


def test_surface_epoch_mismatch_is_reported() -> None:
    digests = _surface_digests()
    receipts = tuple(_receipt(kind, digest, epoch=(6 if kind == "evidence" else 7)) for kind, digest in digests.items())
    findings = validate_observation_completeness(
        _envelope(receipts),
        expected_component_ids=_component_ids(),
        observed_surface_digests=digests,
    )
    assert "OBSERVATION_SURFACE_EPOCH_MISMATCH" in {row.code for row in findings}


def test_surface_state_digest_mismatch_is_reported() -> None:
    digests = _surface_digests()
    receipts = tuple(_receipt(kind, "wrong-state" if kind == "handoff" else digest) for kind, digest in digests.items())
    findings = validate_observation_completeness(
        _envelope(receipts),
        expected_component_ids=_component_ids(),
        observed_surface_digests=digests,
    )
    assert "OBSERVATION_SURFACE_STATE_DIGEST_MISMATCH" in {row.code for row in findings}
```

- [ ] **Step 3: Run A8 RED**

```bash
python -m pytest -q tests/test_external_core_a8_observation_completeness.py
```

Expected: import/collection failure because `nolane.external_core.observation` does not exist.

- [ ] **Step 4: Commit test-only RED**

```bash
git add tests/test_external_core_a8_observation_completeness.py
git commit -m "test: expose External Core A8 completeness gap"
```

---

### Task 2: A8 GREEN — strict surface contract, receipts and completeness

**Files:**
- Create: `nolane/external_core/observation.py`
- Test: `tests/test_external_core_a8_observation_completeness.py`

**Interfaces produced:**
- Constants `OBSERVATION_SURFACE_PROTOCOL`, `SURFACE_RECEIPT_PROTOCOL`, `OBSERVATION_PROTOCOL`, and `REQUIRED_SURFACE_KINDS`.
- Frozen dataclasses `ObservationFinding`, `CanonicalObservationSurfaceContract`, `SurfaceObservationReceipt`, and `CanonicalObservationEnvelope`.
- Public validator `validate_observation_completeness(envelope, expected_component_ids=..., observed_surface_digests=...)` returning a tuple of `ObservationFinding`.
- All three persisted observation types expose `create`, `to_state`, `from_state`, and `validate_integrity`.

- [ ] **Step 1: Implement strict scalar/key helpers**

```python
def _exact_non_empty_string(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be an exact non-empty string")
    return value


def _exact_epoch(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("observed epoch must be an exact non-negative integer")
    return value
```

Add `_exact_keys` equivalent to A7 strict parsing. Unknown/missing keys fail before restore.

- [ ] **Step 2: Implement `CanonicalObservationSurfaceContract`**

`create(required_component_ids)` rejects non-string/empty IDs and duplicates, sorts component IDs, fixes required kinds to the eight `REQUIRED_SURFACE_KINDS`, and hashes:

```python
payload = {
    "protocol": OBSERVATION_SURFACE_PROTOCOL,
    "required_component_ids": list(component_ids),
    "required_surface_kinds": list(REQUIRED_SURFACE_KINDS),
}
```

`from_state()` accepts exact serialized lists only and requires `dict(state) == expected.to_state()` after reconstruction.

- [ ] **Step 3: Implement `SurfaceObservationReceipt.create`**

Required parameters are `surface_kind`, `provider_id`, `provider_version`, `source_locator`, `scope_digest`, `observed_state_digest`, `enumeration_complete`, and `observed_epoch`. Reject unknown surface kinds, non-bool completeness, bool epochs, empty/coercible strings, duplicate/unknown keys, and forged digest state. Digest protocol plus all semantic fields.

- [ ] **Step 4: Implement final-shape `CanonicalObservationEnvelope`**

Persist exactly these fields:

```text
protocol
surface_contract
observed_epoch
registry_digest
authority_graph_digest
source_state_frontier_digest
evidence_frontier_digest
artifact_frontier_digest
freshness_fence_frontier_digest
handoff_frontier_digest
work_trace_frontier_digest
surface_receipts
chain_id
previous_observation_digest
digest
```

Sort receipts by surface kind but reject duplicate kinds before sorting. `previous_observation_digest` is either `None` or an exact non-empty string. A10 owns genesis semantics.

- [ ] **Step 5: Implement completeness validator**

Emit these deterministic codes:

```text
OBSERVATION_REQUIRED_COMPONENT_MISSING
OBSERVATION_UNEXPECTED_COMPONENT
OBSERVATION_REQUIRED_SURFACE_MISSING
OBSERVATION_SURFACE_DUPLICATE
OBSERVATION_SURFACE_UNEXPECTED
OBSERVATION_ENUMERATION_INCOMPLETE
OBSERVATION_SURFACE_EPOCH_MISMATCH
OBSERVATION_SURFACE_STATE_DIGEST_MISMATCH
OBSERVATION_SURFACE_SCOPE_MISMATCH
```

Never convert missing surface evidence to an empty digest.

- [ ] **Step 6: Run A8 GREEN and frozen regressions**

```bash
python -m pytest -q tests/test_external_core_a8_observation_completeness.py
python -m pytest -q tests/test_external_core_a5_*.py tests/test_external_core_a6_*.py tests/test_external_core_a7_*.py
```

Expected: all pass.

- [ ] **Step 7: Commit A8 GREEN**

```bash
git add nolane/external_core/observation.py tests/test_external_core_a8_observation_completeness.py
git commit -m "feat: add External Core A8 observation completeness"
```

---

### Task 3: A9 RED — provenance substitution

**Files:**
- Create: `tests/test_external_core_a9_observation_provenance.py`

**Interfaces:**
- Consumes A8 receipt/envelope.
- Produces failing expectations for provider identity, version, path, scope, content and epoch binding.

- [ ] **Step 1: Add a helper that reconstructs one receipt with one changed field**

```python
def _receipt_with(receipt: SurfaceObservationReceipt, **changes: object) -> SurfaceObservationReceipt:
    values = {
        "surface_kind": receipt.surface_kind,
        "provider_id": receipt.provider_id,
        "provider_version": receipt.provider_version,
        "source_locator": receipt.source_locator,
        "scope_digest": receipt.scope_digest,
        "observed_state_digest": receipt.observed_state_digest,
        "enumeration_complete": receipt.enumeration_complete,
        "observed_epoch": receipt.observed_epoch,
    }
    values.update(changes)
    return SurfaceObservationReceipt.create(**values)
```

Use an equivalent envelope reconstruction helper; do not add test-only mutation methods to production classes.

- [ ] **Step 2: Add exact provenance cases**

```python
def test_registry_provider_identity_substitution_is_rejected(clean_envelope, provider_expectations) -> None:
    receipt = clean_envelope.surface_receipt("registry")
    candidate = _replace_receipt(clean_envelope, _receipt_with(receipt, provider_id="provider:substitute"))
    findings = validate_observation_provenance(candidate, provider_expectations=provider_expectations)
    assert "OBSERVATION_PROVIDER_ID_MISMATCH" in {row.code for row in findings}


def test_authority_graph_provider_version_substitution_is_rejected(clean_envelope, provider_expectations) -> None:
    receipt = clean_envelope.surface_receipt("authority-graph")
    candidate = _replace_receipt(clean_envelope, _receipt_with(receipt, provider_version="999"))
    findings = validate_observation_provenance(candidate, provider_expectations=provider_expectations)
    assert "OBSERVATION_PROVIDER_VERSION_MISMATCH" in {row.code for row in findings}


def test_registry_source_locator_substitution_is_rejected(clean_envelope, provider_expectations) -> None:
    receipt = clean_envelope.surface_receipt("registry")
    candidate = _replace_receipt(clean_envelope, _receipt_with(receipt, source_locator="tests:wrong-source"))
    findings = validate_observation_provenance(candidate, provider_expectations=provider_expectations)
    assert "OBSERVATION_SOURCE_LOCATOR_MISMATCH" in {row.code for row in findings}
```

The production convenience `surface_receipt(kind)` is allowed because audit integration also needs exact lookup. `_replace_receipt` remains test-local reconstruction.

- [ ] **Step 3: Run and commit A9 RED**

```bash
python -m pytest -q tests/test_external_core_a9_observation_provenance.py
git add tests/test_external_core_a9_observation_provenance.py
git commit -m "test: expose External Core A9 provenance gap"
```

Expected before GREEN: import failure for provider expectation/provenance validator API.

---

### Task 4: A9 GREEN — exact provider/source binding

**Files:**
- Modify: `nolane/external_core/observation.py`
- Test: `tests/test_external_core_a9_observation_provenance.py`

**Interfaces produced:**
- Frozen runtime value `CanonicalSurfaceProviderExpectation(surface_kind, provider_id, provider_version, source_locator)`.
- `validate_observation_provenance(envelope, provider_expectations=...)` returning deterministic `ObservationFinding` rows.
- `CanonicalObservationEnvelope.surface_receipt(surface_kind)` exact lookup used by audit and tests.

- [ ] **Step 1: Implement strict provider expectation values**

Registry and graph expectations are exactly:

```text
registry provider_id: external-core:canonical-registry
registry provider_version: 1
registry source_locator: nolane.external_core.audit:build_canonical_registry
authority-graph provider_id: external-core:canonical-authority-graph
authority-graph provider_version: 1
authority-graph source_locator: nolane.external_core.audit:build_canonical_fabric_profile
```

- [ ] **Step 2: Implement provenance validator**

Required codes:

```text
OBSERVATION_PROVIDER_ID_MISMATCH
OBSERVATION_PROVIDER_VERSION_MISMATCH
OBSERVATION_SOURCE_LOCATOR_MISMATCH
OBSERVATION_PROVENANCE_SCOPE_MISMATCH
OBSERVATION_PROVENANCE_CONTENT_MISMATCH
OBSERVATION_PROVENANCE_EPOCH_MISMATCH
OBSERVATION_RECEIPT_FORGED
```

Validate receipt integrity first; compare exact provider values; compare receipt epoch to envelope epoch; compare receipt state digest to the matching envelope commitment.

- [ ] **Step 3: Run A8+A9 and commit GREEN**

```bash
python -m pytest -q tests/test_external_core_a8_*.py tests/test_external_core_a9_*.py
git add nolane/external_core/observation.py tests/test_external_core_a9_observation_provenance.py
git commit -m "feat: add External Core A9 observation provenance"
```

Expected: all pass.

---

### Task 5: A10 RED — predecessor and fork semantics

**Files:**
- Create: `tests/test_external_core_a10_observation_continuity.py`

**Interfaces:**
- Consumes A8/A9 envelope.
- Produces failing transition/fork expectations.

- [ ] **Step 1: Add test-local successor reconstruction**

`_successor(previous, epoch, chain_id, previous_digest, salt)` must rebuild every receipt at the new epoch and alter one source-state observed digest using `salt`, then create a new envelope with `previous_observation_digest` equal to the supplied predecessor digest.

- [ ] **Step 2: Add exact continuity cases**

```python
def test_successor_requires_exact_predecessor_digest(previous) -> None:
    current = _successor(previous, epoch=previous.observed_epoch + 1, previous_digest="wrong", chain_id=previous.chain_id, salt="one")
    findings = validate_observation_transition(previous, current)
    assert "OBSERVATION_PREDECESSOR_DIGEST_MISMATCH" in {row.code for row in findings}


def test_successor_requires_same_chain_id(previous) -> None:
    current = _successor(previous, epoch=previous.observed_epoch + 1, previous_digest=previous.digest, chain_id="external-core:other", salt="two")
    findings = validate_observation_transition(previous, current)
    assert "OBSERVATION_CHAIN_ID_MISMATCH" in {row.code for row in findings}


def test_successor_epoch_must_be_strictly_greater(previous) -> None:
    current = _successor(previous, epoch=previous.observed_epoch, previous_digest=previous.digest, chain_id=previous.chain_id, salt="three")
    findings = validate_observation_transition(previous, current)
    assert "OBSERVATION_EPOCH_NOT_MONOTONIC" in {row.code for row in findings}


def test_missing_predecessor_is_not_silently_genesis(previous) -> None:
    current = _successor(previous, epoch=previous.observed_epoch + 1, previous_digest=previous.digest, chain_id=previous.chain_id, salt="four")
    findings = validate_observation_transition(None, current, genesis=False)
    assert "OBSERVATION_PREDECESSOR_UNAVAILABLE" in {row.code for row in findings}


def test_distinct_sibling_successors_are_a_fork(previous) -> None:
    left = _successor(previous, epoch=previous.observed_epoch + 1, previous_digest=previous.digest, chain_id=previous.chain_id, salt="left")
    right = _successor(previous, epoch=previous.observed_epoch + 1, previous_digest=previous.digest, chain_id=previous.chain_id, salt="right")
    findings = detect_observation_forks((left, right))
    assert [row.code for row in findings] == ["OBSERVATION_FORK_DETECTED"]
```

- [ ] **Step 3: Run and commit A10 RED**

```bash
python -m pytest -q tests/test_external_core_a10_observation_continuity.py
git add tests/test_external_core_a10_observation_continuity.py
git commit -m "test: expose External Core A10 continuity gap"
```

Expected before GREEN: import failure for transition/fork APIs.

---

### Task 6: A10 GREEN — pure continuity/fork validation

**Files:**
- Modify: `nolane/external_core/observation.py`
- Test: `tests/test_external_core_a10_observation_continuity.py`

**Interfaces produced:**
- `validate_observation_transition(previous, current, genesis=False)` returning deterministic findings.
- `detect_observation_forks(successors)` returning deterministic findings.

- [ ] **Step 1: Implement transition validation**

Exact codes:

```text
OBSERVATION_PREDECESSOR_UNAVAILABLE
OBSERVATION_PREDECESSOR_DIGEST_MISMATCH
OBSERVATION_CHAIN_ID_MISMATCH
OBSERVATION_EPOCH_NOT_MONOTONIC
OBSERVATION_GENESIS_CONTEXT_INVALID
```

`genesis=True` requires no predecessor object and `current.previous_observation_digest is None`. `genesis=False` requires predecessor evidence. Successor requires exact predecessor digest, exact chain ID, and `current.observed_epoch > previous.observed_epoch`. Validate envelope integrity before comparisons.

- [ ] **Step 2: Implement deterministic fork detection**

Validate each envelope, group by `(chain_id, previous_observation_digest)`, ignore exact duplicate successor digests, and emit one `OBSERVATION_FORK_DETECTED` finding for each group containing more than one distinct digest. Sort findings by chain ID then predecessor digest.

- [ ] **Step 3: Run all observation tests and commit GREEN**

```bash
python -m pytest -q tests/test_external_core_a8_*.py tests/test_external_core_a9_*.py tests/test_external_core_a10_*.py
git add nolane/external_core/observation.py tests/test_external_core_a10_observation_continuity.py
git commit -m "feat: add External Core A10 observation continuity"
```

Expected: all pass.

---

### Task 7: Integrate observation-v1 into the current admission/audit lane

**Files:**
- Modify: `nolane/external_core/integration_admission_bundle.py`
- Modify: `nolane/external_core/observation.py`
- Test: A7/A8/A9/A10 tests.

**Interfaces produced:**
- `build_canonical_observation` with explicit epoch, chain, predecessor digest, and six non-optional frontier mappings.
- `run_canonical_admission_audit` gains keyword-only `current_observation`, `predecessor_observation`, `competing_successors`, and `observation_genesis` inputs.
- `CanonicalAdmissionAuditReport` gains `observation_digest` and includes it in the v4 report digest.

- [ ] **Step 1: Write integration RED tests first**

```python
def test_current_audit_requires_complete_surface_witness() -> None:
    report = run_canonical_admission_audit(bundle=persisted_bundle, current_observed_epoch=7)
    assert "CURRENT_OBSERVATION_WITNESS_UNAVAILABLE" in {row.code for row in report.findings}


def test_current_audit_rejects_provider_substitution() -> None:
    report = run_canonical_admission_audit(
        bundle=persisted_bundle,
        current_observed_epoch=7,
        current_observation=provider_substituted_observation,
        predecessor_observation=predecessor,
    )
    assert "OBSERVATION_PROVIDER_ID_MISMATCH" in {row.code for row in report.findings}


def test_fresh_capture_reads_current_objects_once(monkeypatch) -> None:
    reads = {"count": 0}
    original = admission_bundle._strict_current_objects
    def counted():
        reads["count"] += 1
        return original()
    monkeypatch.setattr(admission_bundle, "_strict_current_objects", counted)
    report = admission_bundle.run_canonical_admission_audit(
        observed_epoch=7,
        observation_genesis=True,
        current_source_state_digests={},
        current_evidence_digests={},
        current_artifact_digests={},
        current_freshness_fences={},
        known_handoff_digests={},
        current_work_trace_digests={},
    )
    assert not report.findings
    assert reads == {"count": 1}
```

- [ ] **Step 2: Implement one capture path**

Capture in this order: strict-snapshot six mappings once; capture registry/profile once; compute detached state digests; create registry/graph receipts and six dynamic receipts at the same epoch; build one observation envelope; build the admission bundle from the same registry/profile/snapshot objects. Dynamic caller-provider receipts use stable IDs such as `external-core:caller-source-state` and explicitly state complete enumeration; they do not assert truthfulness.

- [ ] **Step 3: Upgrade current audit report schema**

Persist exactly `protocol`, `observation_digest`, `findings`, and `digest`. Include observation digest in report digest payload. This is a current audit protocol change only.

- [ ] **Step 4: Enforce persisted audit order**

For persisted v4 audit: bundle integrity; current observation integrity; exact envelope/context registry/graph/six frontier/epoch equality; A8 completeness; A9 provenance; A10 transition and supplied sibling fork detection; existing A5/A6/A7 re-admission checks. Missing observation witness emits `CURRENT_OBSERVATION_WITNESS_UNAVAILABLE`; never regenerate provenance from partial historical inputs.

- [ ] **Step 5: Run focused tests and commit**

```bash
python -m pytest -q tests/test_external_core_a7_*.py tests/test_external_core_a8_*.py tests/test_external_core_a9_*.py tests/test_external_core_a10_*.py
git add nolane/external_core/observation.py nolane/external_core/integration_admission_bundle.py tests/test_external_core_a8_*.py tests/test_external_core_a9_*.py tests/test_external_core_a10_*.py
git commit -m "feat: integrate final External Core observation witness"
```

Expected: all pass.

---

### Task 8: Final current-lane version/protocol closure

**Files:**
- Modify: `nolane/external_core/integration.py`
- Modify: `nolane/external_core/compatibility.py`
- Modify: `nolane/external_core/integration_admission_bundle.py`
- Modify: `nolane/metadata/component_versions.py`
- Modify current projection tests found by repository search for `external.integration` and `0.0.6`.

- [ ] **Step 1: Capture expected version-discipline RED**

Run against base `63f3d3a89e93fc92868dc0829b6a15777283e74d` before bump. Expected: semantic change without owner revision for `external.integration`.

- [ ] **Step 2: Apply exact final identities**

```text
nolane.external_core.integration.COMPONENT_VERSION = 0.0.7
nolane.external_core.compatibility.SEMANTIC_SURFACE_VERSION = 0.0.7
nolane.external_core.integration_admission_bundle.COMPONENT_VERSION = 0.0.7
external.integration metadata revision = 7
ADMISSION_AUDIT_PROTOCOL = external-integration-admission-audit-v4
audit digest prefix = admission-audit-v4-
OBSERVATION_PROTOCOL = external-canonical-observation-v1
```

Preserve exactly:

```text
nolane.external_core.integration_admission.COMPONENT_VERSION = 0.0.4
ADMISSION_PROTOCOL = external-integration-admission-v2
ADMISSION_BUNDLE_PROTOCOL = external-integration-admission-bundle-v2
```

- [ ] **Step 3: Update current projection assertions only**

Historical owner/protocol assertions in A5/A6/A7 remain unchanged.

- [ ] **Step 4: Verify version/projected surfaces and commit**

```bash
python -m pytest -q tests/test_refoundation_component_versions.py
python -m nolane.metadata.version_discipline_cli --base 63f3d3a89e93fc92868dc0829b6a15777283e74d --head HEAD --check
git add nolane/external_core/integration.py nolane/external_core/compatibility.py nolane/external_core/integration_admission_bundle.py nolane/metadata/component_versions.py tests
git commit -m "chore: close External Core v1 at integration 0.0.7"
```

Expected: projection pass and zero version-discipline findings after the bump.

---

### Task 9: CI and CURRENT seal

**Files:**
- Modify: `.github/workflows/external-core-a2.yml`
- Modify: `CURRENT/EXTERNAL_CORE.md`

- [ ] **Step 1: Extend External Core contract glob**

Include all A8, A9 and A10 test files. Rename the audit step to `Verify canonical A10 External Core v1 admission audit` and the JSON output to `/tmp/external-core-a10-admission-audit.json`.

- [ ] **Step 2: Append zero-loss CURRENT sections**

Append `Post-Epoch-0 A8 — Observation Completeness`, `Post-Epoch-0 A9 — Observation Provenance`, and `Post-Epoch-0 A10 — Observation Continuity / External Core v1 Architecture Complete`. State explicitly that fork detection works only on supplied competing evidence and External Core owns no mutable chain head.

- [ ] **Step 3: Check and commit**

```bash
git diff --check
git add .github/workflows/external-core-a2.yml CURRENT/EXTERNAL_CORE.md
git commit -m "docs: seal External Core v1 architecture at A10"
```

Expected: whitespace check clean.

---

### Task 10: Full verification, PR, merge and production seal

**Files:**
- No production edits unless a fresh current regression proves a defect.

- [ ] **Step 1: Fresh feature-head verification**

```bash
python -m py_compile nolane/core/*.py nolane/external_core/*.py nolane/metadata/*.py
python -m pytest -q tests/test_external_core_g*.py tests/test_external_core_a2_*.py tests/test_external_core_a3_*.py tests/test_external_core_version_discipline*.py tests/test_external_core_integration_*.py tests/test_external_core_scoped_*.py tests/test_external_core_a5_*.py tests/test_external_core_a6_*.py tests/test_external_core_a7_*.py tests/test_external_core_a8_*.py tests/test_external_core_a9_*.py tests/test_external_core_a10_*.py
python -m pytest -q tests/test_refoundation_component_versions.py
python -m nolane.external_core.audit --check
python -m nolane.external_core.integration_admission_bundle --check
python -m pytest -q tests/test_coding_agi_ops_*.py tests/test_coding_agi_research_*.py tests/test_coding_agi_assurance_*.py
git diff --check
```

Require every command green.

- [ ] **Step 2: Version discipline on exact A7→A10 boundary**

Require `clean=true` and an empty findings array for base `63f3d3a89e93fc92868dc0829b6a15777283e74d` to exact feature head.

- [ ] **Step 3: Open draft PR and record exact evidence**

PR body records all RED/GREEN heads, exact test counts, current/frozen protocol identities and final boundary SHA.

- [ ] **Step 4: Require External Core Python 3.11 and 3.13 acceptance**

Both jobs pass compile, all External Core contracts, version discipline, component projection, A2+A3 audit, final A10 audit, and prior G/Assurance regressions.

- [ ] **Step 5: Run broad current gates**

Require current Refoundation, Memory, E Acting, R1.9, R2.0i, R2.63/R2.64.1 and applicable replacement-evidence gates. Historical R2.62/R2.65/R2.66/R2.67.1 full-release reds may be classified only from fresh logs proving the known frozen boundary and no A8–A10 involvement.

- [ ] **Step 6: Verify synthetic merge-ref**

Require parent 1 = current production main, parent 2 = exact feature head, no merge-only tree drift, valid GitHub signature, and zero unresolved review/thread blockers.

- [ ] **Step 7: Merge with exact expected head SHA**

Use merge commit. Any head drift fails closed.

- [ ] **Step 8: Post-merge production verification**

Verify production `main` SHA/tree/parents/signature and a fresh post-merge External Core run on Python 3.11/3.13. Re-run version discipline on A7→A10 boundary and require final A10 audit clean.

- [ ] **Step 9: Freeze architectural generation**

Only after production verification, declare `External Core v1 Architecture Complete — A1 through A10 frozen architectural generation.` Do not create A11 as part of this work.
