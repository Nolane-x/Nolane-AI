# External Core A8–A10 v1 Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the common External Core architectural generation at A10 by adding complete-surface observation, provenance-bound observation receipts, and caller-evidence-driven continuity/fork validation while preserving all frozen A5–A7 artifact identities.

**Architecture:** Add one focused `nolane.external_core.observation` module containing the final reusable observation model. A8, A9 and A10 are implemented as separate TDD milestones against that one model, then `integration_admission_bundle.py` consumes the observation envelope in the current audit lane. Frozen admission-v2 and bundle-v2 remain byte-semantically unchanged; the final current lane advances once to `external.integration 0.0.7` and audit-v4.

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

- Create `nolane/external_core/observation.py` — owns surface contracts, surface receipts, canonical observation envelopes, strict serialization, completeness/provenance validation, transition validation and fork detection.
- Modify `nolane/external_core/integration_admission_bundle.py` — captures/consumes one observation envelope in the current build/audit lane; does not duplicate observation-model logic.
- Modify `nolane/external_core/integration.py` — current component version only at final closure.
- Modify `nolane/external_core/compatibility.py` — current semantic projection only at final closure.
- Modify `nolane/metadata/component_versions.py` — `external.integration` revision only at final closure.
- Modify `.github/workflows/external-core-a2.yml` — include A8/A9/A10 tests and final A10 audit naming.
- Modify `CURRENT/EXTERNAL_CORE.md` — append A8/A9/A10 closure without rewriting A2–A7 history.
- Create `tests/test_external_core_a8_observation_completeness.py` — A8 RED/GREEN.
- Create `tests/test_external_core_a9_observation_provenance.py` — A9 RED/GREEN.
- Create `tests/test_external_core_a10_observation_continuity.py` — A10 RED/GREEN.
- Update current projection/revalidation tests only where they assert the current `external.integration` semantic surface.

---

### Task 1: A8 RED — prove completeness is missing after A7

**Files:**
- Create: `tests/test_external_core_a8_observation_completeness.py`
- Read only: `nolane/external_core/integration_admission_bundle.py`
- Read only: `nolane/external_core/audit.py`

**Interfaces:**
- Consumes: `build_canonical_registry()`, `build_canonical_fabric_profile()`, `canonical_frontier_digest()` and A7 current audit APIs.
- Produces: failing behavioral expectations that define A8 negative-space semantics.

- [ ] **Step 1: Write failing tests for missing observation representation**

Create tests whose imports intentionally fail before `observation.py` exists:

```python
from nolane.external_core.observation import (
    CanonicalObservationSurfaceContract,
    SurfaceObservationReceipt,
    CanonicalObservationEnvelope,
    REQUIRED_SURFACE_KINDS,
)


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
```

- [ ] **Step 2: Add A8 behavior tests**

Include concrete tests for:

```python
def test_surface_contract_rejects_missing_required_surface() -> None:
    ...


def test_surface_contract_rejects_unexpected_surface() -> None:
    ...


def test_surface_contract_rejects_incomplete_component_population() -> None:
    ...


def test_required_surface_receipt_must_declare_complete_enumeration() -> None:
    ...


def test_required_surface_receipt_epoch_must_match_observation_epoch() -> None:
    ...


def test_required_surface_receipt_digest_must_match_detached_snapshot() -> None:
    ...


def test_none_surface_is_not_equivalent_to_explicit_empty_surface() -> None:
    ...
```

Use exact strings and exact non-negative integer epochs. Include `True` as an invalid epoch case.

- [ ] **Step 3: Run A8 RED**

Run:

```bash
python -m pytest -q tests/test_external_core_a8_observation_completeness.py
```

Expected: FAIL because the observation model and/or A8 completeness enforcement does not exist.

- [ ] **Step 4: Commit test-only RED**

```bash
git add tests/test_external_core_a8_observation_completeness.py
git commit -m "test: expose External Core A8 completeness gap"
```

---

### Task 2: A8 GREEN — add strict surface contract, receipts and completeness validation

**Files:**
- Create: `nolane/external_core/observation.py`
- Test: `tests/test_external_core_a8_observation_completeness.py`

**Interfaces:**
- Produces:
  - `OBSERVATION_SURFACE_PROTOCOL = "external-canonical-observation-surface-v1"`
  - `SURFACE_RECEIPT_PROTOCOL = "external-surface-observation-receipt-v1"`
  - `OBSERVATION_PROTOCOL = "external-canonical-observation-v1"`
  - `REQUIRED_SURFACE_KINDS: tuple[str, ...]`
  - `CanonicalObservationSurfaceContract.create(required_component_ids: Sequence[str])`
  - `SurfaceObservationReceipt.create(...)`
  - `CanonicalObservationEnvelope.create(...)`
  - `.to_state()`, `.from_state()`, `.validate_integrity()` on all three types
  - `validate_observation_completeness(envelope, *, expected_component_ids, observed_surface_digests) -> tuple[ObservationFinding, ...]`

- [ ] **Step 1: Implement strict primitives**

Use frozen dataclasses with slots. Add exact helpers equivalent in strictness to A5/A7 patterns:

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

- [ ] **Step 2: Implement `CanonicalObservationSurfaceContract`**

Canonical contract must:
- deduplicate/reject duplicate component IDs rather than silently set-normalizing input;
- sort canonical component IDs and required surface kinds;
- require required surface kinds to equal `REQUIRED_SURFACE_KINDS` exactly;
- content-address its digest;
- reject unknown/missing serialized keys.

- [ ] **Step 3: Implement `SurfaceObservationReceipt`**

Signature:

```python
@classmethod
def create(
    cls,
    *,
    surface_kind: str,
    provider_id: str,
    provider_version: str,
    source_locator: str,
    scope_digest: str,
    observed_state_digest: str,
    enumeration_complete: bool,
    observed_epoch: int,
) -> "SurfaceObservationReceipt": ...
```

Rules:
- `surface_kind` must be in `REQUIRED_SURFACE_KINDS`;
- `enumeration_complete` must be exact bool;
- all strings exact/non-empty;
- epoch exact int/non-negative;
- digest is content-addressed over protocol + all semantic fields.

- [ ] **Step 4: Implement minimal `CanonicalObservationEnvelope` needed for A8**

Create the full final field shape now so A9/A10 do not churn schema:

```python
@classmethod
def create(
    cls,
    *,
    surface_contract: CanonicalObservationSurfaceContract,
    observed_epoch: int,
    registry_digest: str,
    authority_graph_digest: str,
    source_state_frontier_digest: str,
    evidence_frontier_digest: str,
    artifact_frontier_digest: str,
    freshness_fence_frontier_digest: str,
    handoff_frontier_digest: str,
    work_trace_frontier_digest: str,
    surface_receipts: Sequence[SurfaceObservationReceipt],
    chain_id: str,
    previous_observation_digest: str | None,
) -> "CanonicalObservationEnvelope": ...
```

A8 validation may accept `previous_observation_digest=None`; genesis semantics are enforced in A10, not here.

- [ ] **Step 5: Implement `validate_observation_completeness`**

Return deterministic `ObservationFinding(code, detail, subject_id)` rows. Required A8 codes:

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

Do not turn `None` into `{}` inside this model.

- [ ] **Step 6: Run A8 GREEN**

```bash
python -m pytest -q tests/test_external_core_a8_observation_completeness.py
```

Expected: PASS.

- [ ] **Step 7: Run strict serialization regressions**

```bash
python -m pytest -q tests/test_external_core_a5_*.py tests/test_external_core_a6_*.py tests/test_external_core_a7_*.py
```

Expected: PASS with no frozen protocol changes.

- [ ] **Step 8: Commit A8 GREEN**

```bash
git add nolane/external_core/observation.py tests/test_external_core_a8_observation_completeness.py
git commit -m "feat: add External Core A8 observation completeness"
```

---

### Task 3: A9 RED — prove provenance substitution remains possible

**Files:**
- Create: `tests/test_external_core_a9_observation_provenance.py`
- Read: `nolane/external_core/observation.py`

**Interfaces:**
- Consumes: A8 contract/receipt/envelope types.
- Produces: failing expectations for exact provider provenance and persisted replay.

- [ ] **Step 1: Write provenance substitution tests**

Construct two receipts with identical state/scope/epoch but different provider identity/source locator and prove A8 completeness alone does not reject the substitution.

Required tests:

```python
def test_provider_identity_substitution_changes_observation_identity() -> None:
    ...


def test_provider_version_substitution_changes_observation_identity() -> None:
    ...


def test_source_locator_substitution_changes_observation_identity() -> None:
    ...


def test_cross_epoch_surface_receipt_reuse_is_blocked() -> None:
    ...


def test_registry_provider_must_match_canonical_provider_expectation() -> None:
    ...


def test_authority_graph_provider_must_match_canonical_provider_expectation() -> None:
    ...
```

- [ ] **Step 2: Run A9 RED**

```bash
python -m pytest -q tests/test_external_core_a9_observation_provenance.py
```

Expected: at least one test fails because there is no dedicated provenance validation API/current-provider expectation yet.

- [ ] **Step 3: Commit test-only RED**

```bash
git add tests/test_external_core_a9_observation_provenance.py
git commit -m "test: expose External Core A9 provenance gap"
```

---

### Task 4: A9 GREEN — bind provider identity, source, scope, content and epoch

**Files:**
- Modify: `nolane/external_core/observation.py`
- Test: `tests/test_external_core_a9_observation_provenance.py`

**Interfaces:**
- Produces:
  - `CanonicalSurfaceProviderExpectation`
  - `validate_observation_provenance(envelope, *, provider_expectations) -> tuple[ObservationFinding, ...]`
  - `surface_receipt_for(...)` or equivalent canonical helper used later by integration audit.

- [ ] **Step 1: Add provider expectation type**

```python
@dataclass(frozen=True, slots=True)
class CanonicalSurfaceProviderExpectation:
    surface_kind: str
    provider_id: str
    provider_version: str
    source_locator: str
```

Use strict exact fields and content-addressed digest only if serialized/persisted; otherwise keep it a pure runtime expectation value.

- [ ] **Step 2: Implement provenance validation**

Required deterministic codes:

```text
OBSERVATION_PROVIDER_ID_MISMATCH
OBSERVATION_PROVIDER_VERSION_MISMATCH
OBSERVATION_SOURCE_LOCATOR_MISMATCH
OBSERVATION_PROVENANCE_SCOPE_MISMATCH
OBSERVATION_PROVENANCE_CONTENT_MISMATCH
OBSERVATION_PROVENANCE_EPOCH_MISMATCH
OBSERVATION_RECEIPT_FORGED
```

Do not claim provider truthfulness. Only bind identity/path/scope/content/epoch.

- [ ] **Step 3: Make registry and authority-graph expectations canonical**

Build expectations from the current canonical in-process builder path using explicit provider IDs such as:

```text
external-core:canonical-registry
external-core:canonical-authority-graph
```

and exact source locators tied to the canonical builder functions/modules. Do not use display strings derived from arbitrary objects.

- [ ] **Step 4: Run A9 GREEN + A8 regression**

```bash
python -m pytest -q tests/test_external_core_a8_observation_completeness.py tests/test_external_core_a9_observation_provenance.py
```

Expected: PASS.

- [ ] **Step 5: Commit A9 GREEN**

```bash
git add nolane/external_core/observation.py tests/test_external_core_a9_observation_provenance.py
git commit -m "feat: add External Core A9 observation provenance"
```

---

### Task 5: A10 RED — prove continuity and forks are not represented

**Files:**
- Create: `tests/test_external_core_a10_observation_continuity.py`
- Read: `nolane/external_core/observation.py`

**Interfaces:**
- Consumes: A8/A9 envelope.
- Produces: failing expectations for explicit genesis, predecessor binding, monotonic cross-observation epochs, chain IDs and fork classification.

- [ ] **Step 1: Write transition tests**

Required cases:

```python
def test_successor_requires_exact_predecessor_digest() -> None:
    ...


def test_successor_requires_same_chain_id() -> None:
    ...


def test_successor_epoch_must_be_strictly_greater_than_predecessor() -> None:
    ...


def test_genesis_must_be_explicit_not_inferred_from_missing_predecessor() -> None:
    ...
```

- [ ] **Step 2: Write fork test**

Build two individually valid successors with the same `(chain_id, previous_observation_digest)` but different canonical successor digests:

```python
def test_sibling_successors_are_classified_as_observation_fork() -> None:
    findings = detect_observation_forks((left, right))
    assert [row.code for row in findings] == ["OBSERVATION_FORK_DETECTED"]
```

- [ ] **Step 3: Run A10 RED**

```bash
python -m pytest -q tests/test_external_core_a10_observation_continuity.py
```

Expected: FAIL because transition/fork APIs do not exist yet.

- [ ] **Step 4: Commit test-only RED**

```bash
git add tests/test_external_core_a10_observation_continuity.py
git commit -m "test: expose External Core A10 continuity gap"
```

---

### Task 6: A10 GREEN — pure continuity validation and fork detection

**Files:**
- Modify: `nolane/external_core/observation.py`
- Test: `tests/test_external_core_a10_observation_continuity.py`

**Interfaces:**
- Produces:
  - `validate_observation_transition(previous, current, *, genesis=False) -> tuple[ObservationFinding, ...]`
  - `detect_observation_forks(successors: Sequence[CanonicalObservationEnvelope]) -> tuple[ObservationFinding, ...]`

- [ ] **Step 1: Implement transition validation**

Required codes:

```text
OBSERVATION_PREDECESSOR_UNAVAILABLE
OBSERVATION_PREDECESSOR_DIGEST_MISMATCH
OBSERVATION_CHAIN_ID_MISMATCH
OBSERVATION_EPOCH_NOT_MONOTONIC
OBSERVATION_GENESIS_CONTEXT_INVALID
```

Genesis rules:
- `genesis=True` requires `previous is None` and `current.previous_observation_digest is None`;
- `genesis=False` requires predecessor evidence;
- no fallback from missing predecessor to genesis.

Successor rules:
- exact predecessor digest;
- exact chain ID equality;
- `current.observed_epoch > previous.observed_epoch`.

- [ ] **Step 2: Implement pure fork detection**

Group integrity-valid envelopes by `(chain_id, previous_observation_digest)`. Ignore exact duplicate envelope digests. If a group contains more than one distinct successor digest, emit exactly one deterministic `OBSERVATION_FORK_DETECTED` finding for that predecessor group.

- [ ] **Step 3: Run A10 GREEN and all observation tests**

```bash
python -m pytest -q \
  tests/test_external_core_a8_observation_completeness.py \
  tests/test_external_core_a9_observation_provenance.py \
  tests/test_external_core_a10_observation_continuity.py
```

Expected: PASS.

- [ ] **Step 4: Commit A10 GREEN**

```bash
git add nolane/external_core/observation.py tests/test_external_core_a10_observation_continuity.py
git commit -m "feat: add External Core A10 observation continuity"
```

---

### Task 7: Integrate the final observation envelope into current admission/audit lane

**Files:**
- Modify: `nolane/external_core/integration_admission_bundle.py`
- Modify: `nolane/external_core/observation.py`
- Test: all A8/A9/A10 tests plus focused A7 regressions.

**Interfaces:**
- Consumes: `CanonicalObservationEnvelope`, A8/A9/A10 validators.
- Produces:
  - `build_canonical_observation(...) -> CanonicalObservationEnvelope`
  - `run_canonical_admission_audit(..., current_observation: CanonicalObservationEnvelope | None = None, predecessor_observation: CanonicalObservationEnvelope | None = None, competing_successors: Sequence[CanonicalObservationEnvelope] = ())`
  - `CanonicalAdmissionAuditReport` v4 binding `observation_digest`.

- [ ] **Step 1: Write integration RED tests first**

Add to A8/A9/A10 files or a focused current-audit section:

```python
def test_current_audit_cannot_be_clean_without_complete_required_surface_evidence() -> None:
    ...


def test_persisted_audit_rejects_provider_substitution() -> None:
    ...


def test_persisted_audit_requires_explicit_predecessor_for_non_genesis_observation() -> None:
    ...


def test_fresh_audit_builds_bundle_and_observation_from_same_a7_snapshot() -> None:
    ...
```

Expected before integration: FAIL.

- [ ] **Step 2: Add one capture helper**

Implement a single current-lane capture function that:
1. snapshots six frontier mappings once using A7 strict snapshot rules;
2. captures registry/profile once;
3. creates exact registry/graph receipts;
4. requires explicit complete receipts for dynamic frontier surfaces or uses one narrow canonical caller-provider adapter that creates those receipts from the exact detached mapping and explicit completeness declaration;
5. builds both `CanonicalAdmissionBundle` and `CanonicalObservationEnvelope` from the same detached observation.

Do not call `_strict_current_objects()` again inside the same fresh transaction.

- [ ] **Step 3: Bind observation digest into audit report**

Change current audit report schema only:

```python
@dataclass(frozen=True, slots=True)
class CanonicalAdmissionAuditReport:
    protocol: str
    observation_digest: str | None
    findings: tuple[AdmissionAuditFinding, ...]
    digest: str
```

Digest payload includes `observation_digest`.

- [ ] **Step 4: Persisted audit rules**

For persisted current v4 audit:
- require explicit `current_observation` or enough complete inputs to construct one under the same transaction;
- do not silently regenerate provenance from partial old inputs and call it equivalent;
- require envelope/context registry, graph, six frontier digests and epoch to match exactly;
- run completeness then provenance then continuity validators;
- append deterministic findings; never mutate/repair.

- [ ] **Step 5: Preserve old structural restore paths**

`CanonicalAdmissionBundle.from_state()` and admission-v2 receipts remain unchanged. Historical callers may still restore bundle-v2; only a clean *current v4 audit* requires the new observation witness.

- [ ] **Step 6: Run focused integration tests**

```bash
python -m pytest -q \
  tests/test_external_core_a7_*.py \
  tests/test_external_core_a8_*.py \
  tests/test_external_core_a9_*.py \
  tests/test_external_core_a10_*.py
```

Expected: PASS.

- [ ] **Step 7: Commit integration**

```bash
git add nolane/external_core/observation.py nolane/external_core/integration_admission_bundle.py tests/test_external_core_a8_*.py tests/test_external_core_a9_*.py tests/test_external_core_a10_*.py
git commit -m "feat: integrate final External Core observation witness"
```

---

### Task 8: Final protocol/version closure to 0.0.7 and audit-v4

**Files:**
- Modify: `nolane/external_core/integration.py`
- Modify: `nolane/external_core/compatibility.py`
- Modify: `nolane/external_core/integration_admission_bundle.py`
- Modify: `nolane/metadata/component_versions.py`
- Modify: current projection tests identified by grep for `external.integration` current `0.0.6` assertions.

**Interfaces:**
- Produces final public identities:
  - `external.integration == 0.0.7`
  - semantic compatibility surface `0.0.7`
  - metadata revision `7`
  - `ADMISSION_AUDIT_PROTOCOL == "external-integration-admission-audit-v4"`
  - audit digest prefix `admission-audit-v4-`
  - observation protocol `external-canonical-observation-v1`

- [ ] **Step 1: Run version discipline before bump to capture expected RED**

```bash
python -m nolane.metadata.version_discipline_cli --base 63f3d3a89e93fc92868dc0829b6a15777283e74d --head HEAD --check
```

Expected: semantic-change-without-revision finding for `external.integration`.

- [ ] **Step 2: Apply only current-lane bump**

Set:

```text
integration.COMPONENT_VERSION = "0.0.7"
compatibility.SEMANTIC_SURFACE_VERSION = "0.0.7"
integration_admission_bundle.COMPONENT_VERSION = "0.0.7"
component_versions["external.integration"].revision = 7
ADMISSION_AUDIT_PROTOCOL = "external-integration-admission-audit-v4"
```

Keep:

```text
integration_admission.COMPONENT_VERSION = "0.0.4"
ADMISSION_PROTOCOL = "external-integration-admission-v2"
ADMISSION_BUNDLE_PROTOCOL = "external-integration-admission-bundle-v2"
```

- [ ] **Step 3: Update only current projection tests**

Use repository search to update assertions that intentionally represent current `external.integration`. Do not alter historical receipt owner 0.0.4 assertions or historical A5/A6/A7 protocol assertions.

- [ ] **Step 4: Run projection/version gates**

```bash
python -m pytest -q tests/test_refoundation_component_versions.py
python -m nolane.metadata.version_discipline_cli --base 63f3d3a89e93fc92868dc0829b6a15777283e74d --head HEAD --check
```

Expected: projection PASS and version discipline 0 findings.

- [ ] **Step 5: Commit closure**

```bash
git add nolane/external_core/integration.py nolane/external_core/compatibility.py nolane/external_core/integration_admission_bundle.py nolane/metadata/component_versions.py tests/
git commit -m "chore: close External Core v1 at integration 0.0.7"
```

---

### Task 9: CI and CURRENT documentation closure

**Files:**
- Modify: `.github/workflows/external-core-a2.yml`
- Modify: `CURRENT/EXTERNAL_CORE.md`

**Interfaces:**
- Produces final CI coverage for A8/A9/A10 and final architectural declaration.

- [ ] **Step 1: Update workflow test glob**

Ensure contract array includes:

```bash
tests/test_external_core_a8_*.py
tests/test_external_core_a9_*.py
tests/test_external_core_a10_*.py
```

Rename audit step/output to A10/current-v1 closure, e.g.:

```text
Verify canonical A10 External Core v1 admission audit
/tmp/external-core-a10-admission-audit.json
```

- [ ] **Step 2: Append CURRENT sections without rewriting history**

Append three sections:
- `Post-Epoch-0 A8 — Observation Completeness`
- `Post-Epoch-0 A9 — Observation Provenance`
- `Post-Epoch-0 A10 — Observation Continuity / External Core v1 Architecture Complete`

Final wording must explicitly state:
- no governor/stateful ledger;
- fork detection only for supplied competing evidence;
- no Verification/Assurance/authorization/etc authority;
- A1→A10 architectural generation is now frozen as External Core v1.

- [ ] **Step 3: Run docs/workflow diff check**

```bash
git diff --check
```

Expected: clean.

- [ ] **Step 4: Commit docs/CI closure**

```bash
git add .github/workflows/external-core-a2.yml CURRENT/EXTERNAL_CORE.md
git commit -m "docs: seal External Core v1 architecture at A10"
```

---

### Task 10: Full feature verification and PR acceptance

**Files:**
- No production code changes unless a new RED/current regression proves a defect.

**Interfaces:**
- Consumes exact feature head.
- Produces merge-ready evidence package.

- [ ] **Step 1: Fresh local/exact-tree verification**

Run:

```bash
python -m py_compile nolane/core/*.py nolane/external_core/*.py nolane/metadata/*.py
python -m pytest -q tests/test_external_core_g*.py tests/test_external_core_a2_*.py tests/test_external_core_a3_*.py tests/test_external_core_version_discipline*.py tests/test_external_core_integration_*.py tests/test_external_core_scoped_*.py tests/test_external_core_a5_*.py tests/test_external_core_a6_*.py tests/test_external_core_a7_*.py tests/test_external_core_a8_*.py tests/test_external_core_a9_*.py tests/test_external_core_a10_*.py
python -m pytest -q tests/test_refoundation_component_versions.py
python -m nolane.external_core.audit --check
python -m nolane.external_core.integration_admission_bundle --check
python -m pytest -q tests/test_coding_agi_ops_*.py tests/test_coding_agi_research_*.py tests/test_coding_agi_assurance_*.py
git diff --check
```

Expected: all green.

- [ ] **Step 2: Run component-local version discipline**

Against exact production base `63f3d3a89e93fc92868dc0829b6a15777283e74d`, require `clean=true`, `findings=[]`.

- [ ] **Step 3: Open draft PR from exact feature head**

PR body records:
- A8 RED/GREEN evidence;
- A9 RED/GREEN evidence;
- A10 RED/GREEN evidence;
- final protocol/version identities;
- frozen A5–A7 boundaries;
- exact test counts and run IDs.

- [ ] **Step 4: Run External Core on Python 3.11 and 3.13**

Require both jobs green through:
- compile;
- all External Core contracts;
- version discipline;
- component projection;
- A2+A3 coherence audit;
- final A10 current audit;
- prior G/Assurance regressions.

- [ ] **Step 5: Run broad current gates**

Require current Refoundation, Memory, E Acting, R1.9, R2.0i, R2.63/R2.64.1 and relevant replacement-evidence gates to pass or be explicitly classified from fresh logs.

Frozen R2.62/R2.65/R2.66/R2.67.1 full-release failures may be classified only when logs prove the failure is the known historical frozen-boundary witness and no A8–A10 file participates.

- [ ] **Step 6: Verify synthetic merge-ref**

Require:
- parent 1 = current production main;
- parent 2 = exact feature head;
- merge tree introduces no merge-only drift;
- GitHub signature valid;
- zero unresolved review/thread blockers.

- [ ] **Step 7: Merge with exact expected head**

Use merge commit and exact expected head SHA so drift fails closed.

- [ ] **Step 8: Post-merge production verification**

Require `main` SHA/tree/parents/signature and post-merge External Core run on Python 3.11/3.13. Re-run exact production version discipline against A7 base and confirm final A10 audit clean.

- [ ] **Step 9: Declare architecture complete**

Only after post-merge evidence is green, declare:

```text
External Core v1 Architecture Complete — A1 through A10 frozen architectural generation.
```

No A11 is created as part of this work.
