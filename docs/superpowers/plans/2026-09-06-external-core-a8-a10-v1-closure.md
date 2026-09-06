# External Core A8–A10 v1 Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the common External Core architectural generation at A10 by adding complete-surface observation, provenance-bound observation receipts, and caller-evidence-driven continuity/fork validation while preserving all frozen A5–A7 artifact identities.

**Architecture:** Add one focused `nolane.external_core.observation` module containing the final reusable observation model. A8, A9 and A10 are separate TDD milestones against that one model, then `integration_admission_bundle.py` consumes the observation envelope in the current audit lane. Frozen admission-v2 and bundle-v2 remain byte-semantically unchanged; the final current lane advances once to `external.integration 0.0.7` and audit-v4.

**Tech Stack:** Python 3.11/3.13, dataclasses, canonical JSON/digest helpers, pytest, GitHub Actions, existing External Core registry/profile/admission contracts.

**Spec:** `docs/superpowers/specs/2026-09-06-external-core-a8-a10-v1-closure-design.md`

## Global Constraints

- Scope is External Core common boundary only.
- Stop architectural evolution at A10 and declare External Core v1 architecture complete after verified production merge.
- `nolane.external_core.integration_admission.COMPONENT_VERSION` remains exactly `0.0.4`.
- `ADMISSION_PROTOCOL` remains exactly `external-integration-admission-v2`.
- `ADMISSION_BUNDLE_PROTOCOL` remains exactly `external-integration-admission-bundle-v2`.
- Historical A2–A7 states and frozen release witnesses are not rewritten or refrozen.
- External Core remains read-only/descriptive: no execution, authorization, promotion, learning, deployment, repair, migration, runtime registration, stateful chain-head ownership, family H, or central governor.
- A6 exact same-observation epoch equality remains unchanged.
- A7 single-snapshot semantics remain unchanged and are the capture substrate for A8–A10.
- Final current lane target: `external.integration 0.0.7`, compatibility surface `0.0.7`, metadata revision `7`, audit-v4, observation-v1.
- All new parsers are strict before coercion and fail closed on malformed raw state.

---

## File Structure

- Create `nolane/external_core/observation.py` — surface contracts, surface receipts, canonical observation envelopes, strict serialization, completeness/provenance validation, transition validation and fork detection.
- Modify `nolane/external_core/integration_admission_bundle.py` — one capture path and current v4 audit integration.
- Modify `nolane/external_core/integration.py`, `nolane/external_core/compatibility.py`, `nolane/metadata/component_versions.py` — final current-lane version projection only.
- Modify `.github/workflows/external-core-a2.yml` and `CURRENT/EXTERNAL_CORE.md` — final test/audit coverage and architecture seal.
- Create `tests/test_external_core_a8_observation_completeness.py`.
- Create `tests/test_external_core_a9_observation_provenance.py`.
- Create `tests/test_external_core_a10_observation_continuity.py`.
- Update only tests that intentionally project the current `external.integration` version.

---

### Task 1: A8 RED — prove completeness is absent after A7

**Files:**
- Create: `tests/test_external_core_a8_observation_completeness.py`

**Interfaces:**
- Consumes: current canonical registry/profile and frontier digest helpers.
- Produces: failing A8 expectations before `observation.py` exists.

- [ ] **Step 1: Write the test module with exact helpers**

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


def _envelope(*, receipts: tuple[SurfaceObservationReceipt, ...], epoch: int = 7) -> CanonicalObservationEnvelope:
    registry = build_canonical_registry()
    digests = _surface_digests()
    return CanonicalObservationEnvelope.create(
        surface_contract=CanonicalObservationSurfaceContract.create(
            required_component_ids=tuple(row.component_id for row in registry.manifests),
        ),
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

- [ ] **Step 2: Add exact A8 tests**

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
    envelope = _envelope(receipts=receipts)
    findings = validate_observation_completeness(
        envelope,
        expected_component_ids=envelope.surface_contract.required_component_ids,
        observed_surface_digests=digests,
    )
    assert "OBSERVATION_REQUIRED_SURFACE_MISSING" in {row.code for row in findings}


def test_incomplete_enumeration_is_reported() -> None:
    digests = _surface_digests()
    receipts = tuple(
        _receipt(kind, digest, complete=(kind != "source-state"))
        for kind, digest in digests.items()
    )
    findings = validate_observation_completeness(
        _envelope(receipts=receipts),
        expected_component_ids=build_canonical_registry().component_ids,
        observed_surface_digests=digests,
    )
    assert "OBSERVATION_ENUMERATION_INCOMPLETE" in {row.code for row in findings}


def test_surface_epoch_mismatch_is_reported() -> None:
    digests = _surface_digests()
    receipts = tuple(
        _receipt(kind, digest, epoch=(6 if kind == "evidence" else 7))
        for kind, digest in digests.items()
    )
    findings = validate_observation_completeness(
        _envelope(receipts=receipts),
        expected_component_ids=build_canonical_registry().component_ids,
        observed_surface_digests=digests,
    )
    assert "OBSERVATION_SURFACE_EPOCH_MISMATCH" in {row.code for row in findings}


def test_surface_state_digest_mismatch_is_reported() -> None:
    digests = _surface_digests()
    receipts = tuple(
        _receipt(kind, "wrong-state" if kind == "handoff" else digest)
        for kind, digest in digests.items()
    )
    findings = validate_observation_completeness(
        _envelope(receipts=receipts),
        expected_component_ids=build_canonical_registry().component_ids,
        observed_surface_digests=digests,
    )
    assert "OBSERVATION_SURFACE_STATE_DIGEST_MISMATCH" in {row.code for row in findings}
```

If `CanonicalComponentRegistry` does not expose `component_ids`, use `tuple(row.component_id for row in registry.manifests)` consistently in the test before committing RED; do not add a registry API solely for this test.

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

```python
OBSERVATION_SURFACE_PROTOCOL = "external-canonical-observation-surface-v1"
SURFACE_RECEIPT_PROTOCOL = "external-surface-observation-receipt-v1"
OBSERVATION_PROTOCOL = "external-canonical-observation-v1"
REQUIRED_SURFACE_KINDS: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class ObservationFinding:
    code: str
    detail: str
    subject_id: str

@dataclass(frozen=True, slots=True)
class CanonicalObservationSurfaceContract: ...

@dataclass(frozen=True, slots=True)
class SurfaceObservationReceipt: ...

@dataclass(frozen=True, slots=True)
class CanonicalObservationEnvelope: ...

def validate_observation_completeness(
    envelope: CanonicalObservationEnvelope,
    *,
    expected_component_ids: tuple[str, ...],
    observed_surface_digests: Mapping[str, str],
) -> tuple[ObservationFinding, ...]: ...
```

The class bodies above are type/interface declarations in the plan; implementation steps below define their required behavior without leaving code placeholders in the repository.

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

Add `_exact_keys` equivalent to current A7 strict parsing. Unknown/missing keys fail before restore.

- [ ] **Step 2: Implement `CanonicalObservationSurfaceContract`**

`create(required_component_ids)` must reject non-string/empty IDs and duplicates, sort the final tuple, set required kinds to exactly `REQUIRED_SURFACE_KINDS`, and digest this payload:

```python
payload = {
    "protocol": OBSERVATION_SURFACE_PROTOCOL,
    "required_component_ids": list(component_ids),
    "required_surface_kinds": list(REQUIRED_SURFACE_KINDS),
}
```

`from_state()` accepts only exact serialized lists and requires `dict(state) == expected.to_state()` after reconstruction.

- [ ] **Step 3: Implement `SurfaceObservationReceipt`**

Use exact signature:

```python
SurfaceObservationReceipt.create(
    *,
    surface_kind: str,
    provider_id: str,
    provider_version: str,
    source_locator: str,
    scope_digest: str,
    observed_state_digest: str,
    enumeration_complete: bool,
    observed_epoch: int,
) -> SurfaceObservationReceipt
```

Reject unknown surface kinds, non-bool completeness, bool epochs, empty/coercible strings and forged state. Digest protocol + all semantic fields.

- [ ] **Step 4: Implement final-shape `CanonicalObservationEnvelope`**

Fields are fixed now so A9/A10 do not alter serialization:

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

`surface_receipts` is sorted by `surface_kind` but duplicate kinds must be rejected before sorting. `previous_observation_digest` is either `None` or exact non-empty string. Genesis semantics are deferred to A10.

- [ ] **Step 5: Implement completeness validator**

Emit deterministic findings with these exact codes:

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

Compute expected component differences without coercion. Do not map missing surface evidence to an empty digest.

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
- Produces failing expectations for provider identity/path checks.

- [ ] **Step 1: Add concrete provenance tests**

Use an A8 fixture that creates a clean envelope. Add:

```python
def test_provider_identity_substitution_is_rejected(clean_envelope, provider_expectations) -> None:
    receipt = clean_envelope.receipt_for("registry")
    forged = receipt.replace(provider_id="provider:substitute")
    candidate = clean_envelope.replace_surface_receipt(forged)
    findings = validate_observation_provenance(candidate, provider_expectations=provider_expectations)
    assert "OBSERVATION_PROVIDER_ID_MISMATCH" in {row.code for row in findings}


def test_provider_version_substitution_is_rejected(clean_envelope, provider_expectations) -> None:
    receipt = clean_envelope.receipt_for("authority-graph")
    forged = receipt.replace(provider_version="999")
    candidate = clean_envelope.replace_surface_receipt(forged)
    findings = validate_observation_provenance(candidate, provider_expectations=provider_expectations)
    assert "OBSERVATION_PROVIDER_VERSION_MISMATCH" in {row.code for row in findings}


def test_source_locator_substitution_is_rejected(clean_envelope, provider_expectations) -> None:
    receipt = clean_envelope.receipt_for("registry")
    forged = receipt.replace(source_locator="tests:wrong-source")
    candidate = clean_envelope.replace_surface_receipt(forged)
    findings = validate_observation_provenance(candidate, provider_expectations=provider_expectations)
    assert "OBSERVATION_SOURCE_LOCATOR_MISMATCH" in {row.code for row in findings}
```

Do **not** add production `replace` convenience methods merely for tests. In the real test, reconstruct the receipt/envelope through `.create(...)` using changed values. The snippets describe the semantic mutation only.

- [ ] **Step 2: Run A9 RED**

```bash
python -m pytest -q tests/test_external_core_a9_observation_provenance.py
```

Expected: collection/import failure for missing provenance expectation/validator API.

- [ ] **Step 3: Commit test-only RED**

```bash
git add tests/test_external_core_a9_observation_provenance.py
git commit -m "test: expose External Core A9 provenance gap"
```

---

### Task 4: A9 GREEN — exact provider/source binding

**Files:**
- Modify: `nolane/external_core/observation.py`
- Test: `tests/test_external_core_a9_observation_provenance.py`

**Interfaces produced:**

```python
@dataclass(frozen=True, slots=True)
class CanonicalSurfaceProviderExpectation:
    surface_kind: str
    provider_id: str
    provider_version: str
    source_locator: str


def validate_observation_provenance(
    envelope: CanonicalObservationEnvelope,
    *,
    provider_expectations: Mapping[str, CanonicalSurfaceProviderExpectation],
) -> tuple[ObservationFinding, ...]: ...
```

- [ ] **Step 1: Implement strict runtime provider expectation type**

It is not a persisted protocol. Constructor validates exact surface kind and exact non-empty strings. Use explicit registry/graph expectations:

```python
CanonicalSurfaceProviderExpectation(
    surface_kind="registry",
    provider_id="external-core:canonical-registry",
    provider_version="1",
    source_locator="nolane.external_core.audit:build_canonical_registry",
)
CanonicalSurfaceProviderExpectation(
    surface_kind="authority-graph",
    provider_id="external-core:canonical-authority-graph",
    provider_version="1",
    source_locator="nolane.external_core.audit:build_canonical_fabric_profile",
)
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

Call `receipt.validate_integrity()` first. Compare exact provider values, receipt epoch to envelope epoch, and receipt state digest to the envelope's committed digest for the corresponding surface.

- [ ] **Step 3: Run A8+A9**

```bash
python -m pytest -q tests/test_external_core_a8_observation_completeness.py tests/test_external_core_a9_observation_provenance.py
```

Expected: pass.

- [ ] **Step 4: Commit A9 GREEN**

```bash
git add nolane/external_core/observation.py tests/test_external_core_a9_observation_provenance.py
git commit -m "feat: add External Core A9 observation provenance"
```

---

### Task 5: A10 RED — predecessor and fork semantics

**Files:**
- Create: `tests/test_external_core_a10_observation_continuity.py`

**Interfaces:**
- Consumes A8/A9 envelope.
- Produces failing transition/fork expectations.

- [ ] **Step 1: Add exact transition tests**

Create helper `_successor(previous, *, epoch, chain_id=None, previous_digest=None, salt="next")` that reconstructs a new envelope with changed epoch and one receipt content digest so the successor digest is distinct.

Add:

```python
def test_successor_requires_exact_predecessor_digest(previous) -> None:
    current = _successor(previous, epoch=previous.observed_epoch + 1, previous_digest="wrong")
    findings = validate_observation_transition(previous, current)
    assert "OBSERVATION_PREDECESSOR_DIGEST_MISMATCH" in {row.code for row in findings}


def test_successor_requires_same_chain_id(previous) -> None:
    current = _successor(previous, epoch=previous.observed_epoch + 1, chain_id="external-core:other")
    findings = validate_observation_transition(previous, current)
    assert "OBSERVATION_CHAIN_ID_MISMATCH" in {row.code for row in findings}


def test_successor_epoch_must_be_strictly_greater(previous) -> None:
    current = _successor(previous, epoch=previous.observed_epoch)
    findings = validate_observation_transition(previous, current)
    assert "OBSERVATION_EPOCH_NOT_MONOTONIC" in {row.code for row in findings}


def test_missing_predecessor_is_not_silently_genesis(previous) -> None:
    current = _successor(previous, epoch=previous.observed_epoch + 1)
    findings = validate_observation_transition(None, current, genesis=False)
    assert "OBSERVATION_PREDECESSOR_UNAVAILABLE" in {row.code for row in findings}
```

- [ ] **Step 2: Add exact fork test**

```python
def test_distinct_sibling_successors_are_a_fork(previous) -> None:
    left = _successor(previous, epoch=previous.observed_epoch + 1, salt="left")
    right = _successor(previous, epoch=previous.observed_epoch + 1, salt="right")
    findings = detect_observation_forks((left, right))
    assert [row.code for row in findings] == ["OBSERVATION_FORK_DETECTED"]
```

- [ ] **Step 3: Run A10 RED**

```bash
python -m pytest -q tests/test_external_core_a10_observation_continuity.py
```

Expected: import/collection failure for missing transition/fork APIs.

- [ ] **Step 4: Commit RED**

```bash
git add tests/test_external_core_a10_observation_continuity.py
git commit -m "test: expose External Core A10 continuity gap"
```

---

### Task 6: A10 GREEN — pure continuity/fork validation

**Files:**
- Modify: `nolane/external_core/observation.py`
- Test: `tests/test_external_core_a10_observation_continuity.py`

**Interfaces produced:**

```python
def validate_observation_transition(
    previous: CanonicalObservationEnvelope | None,
    current: CanonicalObservationEnvelope,
    *,
    genesis: bool = False,
) -> tuple[ObservationFinding, ...]: ...


def detect_observation_forks(
    successors: Sequence[CanonicalObservationEnvelope],
) -> tuple[ObservationFinding, ...]: ...
```

- [ ] **Step 1: Implement transition validation**

Exact codes:

```text
OBSERVATION_PREDECESSOR_UNAVAILABLE
OBSERVATION_PREDECESSOR_DIGEST_MISMATCH
OBSERVATION_CHAIN_ID_MISMATCH
OBSERVATION_EPOCH_NOT_MONOTONIC
OBSERVATION_GENESIS_CONTEXT_INVALID
```

Rules:
- `genesis=True`: `previous is None` and `current.previous_observation_digest is None` are both required.
- `genesis=False`: predecessor is required.
- successor requires exact predecessor digest and chain ID.
- successor requires `current.observed_epoch > previous.observed_epoch`.
- call both envelope integrity validators before comparisons.

- [ ] **Step 2: Implement deterministic fork detection**

Validate each envelope, group by `(chain_id, previous_observation_digest)`, ignore exact duplicate successor digests, and emit one finding per group with more than one distinct digest. Sort findings by `(chain_id, predecessor_digest)` before return.

- [ ] **Step 3: Run A8+A9+A10**

```bash
python -m pytest -q tests/test_external_core_a8_*.py tests/test_external_core_a9_*.py tests/test_external_core_a10_*.py
```

Expected: pass.

- [ ] **Step 4: Commit A10 GREEN**

```bash
git add nolane/external_core/observation.py tests/test_external_core_a10_observation_continuity.py
git commit -m "feat: add External Core A10 observation continuity"
```

---

### Task 7: Integrate observation-v1 into the current admission/audit lane

**Files:**
- Modify: `nolane/external_core/integration_admission_bundle.py`
- Modify: `nolane/external_core/observation.py`
- Test: A7/A8/A9/A10 tests.

**Interfaces produced:**

```python
def build_canonical_observation(
    *,
    observed_epoch: int,
    chain_id: str,
    previous_observation_digest: str | None,
    current_source_state_digests: Mapping[str, str],
    current_evidence_digests: Mapping[str, str],
    current_artifact_digests: Mapping[str, str],
    current_freshness_fences: Mapping[str, str],
    known_handoff_digests: Mapping[str, str],
    current_work_trace_digests: Mapping[str, str],
) -> CanonicalObservationEnvelope: ...
```

`run_canonical_admission_audit` gains keyword-only inputs:

```python
current_observation: CanonicalObservationEnvelope | None = None
predecessor_observation: CanonicalObservationEnvelope | None = None
competing_successors: Sequence[CanonicalObservationEnvelope] = ()
observation_genesis: bool = False
```

- [ ] **Step 1: Write integration RED tests before production edits**

Add exact tests:

```python
def test_current_v4_audit_requires_complete_surface_witness() -> None:
    report = run_canonical_admission_audit(bundle=persisted_bundle, current_observed_epoch=7)
    assert "CURRENT_OBSERVATION_WITNESS_UNAVAILABLE" in {row.code for row in report.findings}


def test_current_v4_audit_rejects_provider_substitution() -> None:
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

Before integration, at least the first two behaviors must fail.

- [ ] **Step 2: Add one capture helper, not a second observation implementation**

Capture sequence:
1. strict-snapshot all six caller mappings exactly once;
2. capture registry/profile exactly once;
3. compute detached state digests from those snapshots;
4. create canonical registry/graph receipts and dynamic frontier receipts for the same epoch;
5. build `CanonicalObservationEnvelope`;
6. build `CanonicalAdmissionBundle` from the same registry/profile/snapshot objects.

The dynamic caller-provider adapter must explicitly mark enumeration complete and use stable provider IDs such as `external-core:caller-source-state`. It does not assert truthfulness; it asserts that the caller supplied a complete enumeration for that surface.

- [ ] **Step 3: Upgrade current audit report schema**

Final schema:

```python
@dataclass(frozen=True, slots=True)
class CanonicalAdmissionAuditReport:
    protocol: str
    observation_digest: str | None
    findings: tuple[AdmissionAuditFinding, ...]
    digest: str
```

Include `observation_digest` in report digest payload. This is a current audit protocol change only.

- [ ] **Step 4: Persisted audit validation order**

For persisted v4 current audit:
1. bundle integrity;
2. current observation integrity;
3. exact envelope/context registry/graph/six frontier/epoch equality;
4. A8 completeness;
5. A9 provenance;
6. A10 transition; and supplied sibling fork detection;
7. existing A5/A6/A7 live re-admission checks.

Missing current observation emits `CURRENT_OBSERVATION_WITNESS_UNAVAILABLE`; do not silently reconstruct provenance from old partial inputs.

- [ ] **Step 5: Run focused tests**

```bash
python -m pytest -q tests/test_external_core_a7_*.py tests/test_external_core_a8_*.py tests/test_external_core_a9_*.py tests/test_external_core_a10_*.py
```

Expected: pass.

- [ ] **Step 6: Commit integration**

```bash
git add nolane/external_core/observation.py nolane/external_core/integration_admission_bundle.py tests/test_external_core_a8_*.py tests/test_external_core_a9_*.py tests/test_external_core_a10_*.py
git commit -m "feat: integrate final External Core observation witness"
```

---

### Task 8: Final current-lane version/protocol closure

**Files:**
- Modify: `nolane/external_core/integration.py`
- Modify: `nolane/external_core/compatibility.py`
- Modify: `nolane/external_core/integration_admission_bundle.py`
- Modify: `nolane/metadata/component_versions.py`
- Modify: current projection tests found by repository search for `external.integration` and `0.0.6`.

- [ ] **Step 1: Capture expected version-discipline RED**

Run version discipline against base `63f3d3a89e93fc92868dc0829b6a15777283e74d` before bump. Expected: semantic change without owner revision for `external.integration`.

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

- [ ] **Step 3: Update only current projection assertions**

Do not change historical owner/protocol assertions in A5/A6/A7 tests.

- [ ] **Step 4: Verify version/projected surfaces**

```bash
python -m pytest -q tests/test_refoundation_component_versions.py
python -m nolane.metadata.version_discipline_cli --base 63f3d3a89e93fc92868dc0829b6a15777283e74d --head HEAD --check
```

Expected: projection pass and zero findings.

- [ ] **Step 5: Commit closure**

```bash
git add nolane/external_core/integration.py nolane/external_core/compatibility.py nolane/external_core/integration_admission_bundle.py nolane/metadata/component_versions.py tests
git commit -m "chore: close External Core v1 at integration 0.0.7"
```

---

### Task 9: CI and CURRENT seal

**Files:**
- Modify: `.github/workflows/external-core-a2.yml`
- Modify: `CURRENT/EXTERNAL_CORE.md`

- [ ] **Step 1: Extend External Core contract glob**

Include:

```bash
tests/test_external_core_a8_*.py
tests/test_external_core_a9_*.py
tests/test_external_core_a10_*.py
```

Rename the canonical audit step/output to:

```text
Verify canonical A10 External Core v1 admission audit
/tmp/external-core-a10-admission-audit.json
```

- [ ] **Step 2: Append zero-loss CURRENT sections**

Append A8 completeness, A9 provenance, A10 continuity. Final A10 paragraph must explicitly state:

```text
External Core v1 Architecture Complete — A1 through A10 frozen architectural generation.
```

Also state that fork detection operates only on supplied competing evidence and External Core owns no mutable chain head.

- [ ] **Step 3: Run whitespace check and commit**

```bash
git diff --check
git add .github/workflows/external-core-a2.yml CURRENT/EXTERNAL_CORE.md
git commit -m "docs: seal External Core v1 architecture at A10"
```

---

### Task 10: Full verification, PR, merge and production seal

**Files:**
- No production edits unless a fresh current regression demonstrates a defect.

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

Require `clean=true` and `findings=[]` for base `63f3d3a89e93fc92868dc0829b6a15777283e74d` to exact feature head.

- [ ] **Step 3: Open draft PR and record exact evidence**

PR body records all RED/GREEN heads, exact test counts, current/frozen protocol identities and final boundary SHA.

- [ ] **Step 4: Require External Core Python 3.11 and 3.13 acceptance**

Both jobs must pass compile, all External Core contracts, version discipline, component projection, A2+A3 audit, final A10 audit and prior G/Assurance regressions.

- [ ] **Step 5: Run broad current gates**

Require current Refoundation, Memory, E Acting, R1.9, R2.0i, R2.63/R2.64.1 and applicable replacement-evidence gates. Historical R2.62/R2.65/R2.66/R2.67.1 full-release reds may be classified only from fresh logs proving the known frozen boundary and no A8–A10 involvement.

- [ ] **Step 6: Verify synthetic merge-ref**

Require parent 1 = current production main, parent 2 = exact feature head, no merge-only tree drift, valid GitHub signature, zero unresolved review/thread blockers.

- [ ] **Step 7: Merge with exact expected head SHA**

Use merge commit. Any head drift must fail closed.

- [ ] **Step 8: Post-merge production verification**

Verify production `main` SHA/tree/parents/signature and a fresh post-merge External Core run on Python 3.11/3.13. Re-run version discipline on A7→A10 boundary and require final A10 audit clean.

- [ ] **Step 9: Freeze architectural generation**

Only after production verification, declare External Core v1 complete and do not create A11 as part of this work.
