# Refoundation Epoch 0 Wave 5O — Native Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut `external.architecture` over to native canonical implementation ownership while preserving accepted Architecture behavior and historical import compatibility.

**Architecture:** Move the accepted Architecture graph/control-plane implementation into `nolane.external_core.architecture`, turn the historical module into an exact-object bridge, and update only the component/facade/implementation ledgers required to remove this one native-debt entry. Do not redesign Part-IV behavior or pull Integration into the same migration.

**Tech Stack:** Python 3.11/3.13, standard-library dataclasses/enums, pytest, GitHub Actions, existing Refoundation repository audit.

**Spec:** `docs/superpowers/specs/2026-08-24-refoundation-wave5o-native-architecture-design.md`

## Global Constraints

- Base branch is `refoundation/epoch0-wave5n-native-planning`.
- Preserve exactly 67 permanent first-generation AI identities.
- Preserve historical evidence and import provenance; no destructive history cleanup.
- `external.architecture` alone advances from `0.0.0` to `0.0.1`.
- Generated audit truth must come from `nolane.repository.audit`, never hand edits.
- Canonical Architecture may not reverse-import `cogcoder.organization.architecture`.
- Integration, ADR, change-impact, leases, execution, coding, assurance, evaluation and neural semantics are out of scope.
- Hosted acceptance must be exact-head Python 3.11/3.13 green before review readiness.

---

### Task 1: Freeze Wave 5O ownership contracts and prove RED

**Files:**
- Create: `docs/superpowers/specs/2026-08-24-refoundation-wave5o-native-architecture-design.md`
- Create: `docs/superpowers/plans/2026-08-24-refoundation-wave5o-native-architecture.md`
- Create: `tests/test_refoundation_wave5o_native_architecture.py`

**Consumes:** existing `cogcoder.organization.architecture`, `nolane.external_core.architecture`, Refoundation version/facade/implementation ledgers.

**Produces:** executable acceptance contract for canonical ownership, historical identity bridge, unchanged graph semantics, metadata migration and debt count.

- [ ] Write ownership tests asserting all eleven public Architecture objects have `__module__ == "nolane.external_core.architecture"` and canonical metadata is `external.architecture` / `0.0.1` / historical provenance path.
- [ ] Write AST/source test rejecting any canonical import of `cogcoder.organization.architecture` and requiring canonical digest authority from `nolane.core.canonical_digest`.
- [ ] Write historical bridge identity test for every public object.
- [ ] Write behavior-preservation tests for atomic dependency-cycle rejection and exact state round-trip.
- [ ] Write implementation-ledger/facade/version assertions and generated-debt target 30.
- [ ] Open a draft PR against Wave 5N and require the Refoundation gate to fail specifically on Wave 5O contracts before production changes.

Expected RED causes on the Wave 5N base:

```text
canonical public classes report cogcoder.organization.architecture
COMPONENT_VERSION is 0.0.0
canonical source reverse-imports historical Architecture
external.architecture remains an active facade
external.architecture remains non-native debt (31 total)
```

---

### Task 2: Move accepted Architecture implementation to canonical ownership

**Files:**
- Replace: `nolane/external_core/architecture.py`
- Replace: `cogcoder/organization/architecture.py`
- Test: `tests/test_refoundation_wave5o_native_architecture.py`
- Regression: `tests/test_coding_agi_architecture_*.py`

**Interfaces:**
- Consumes: `canonical_digest` from `nolane.core.canonical_digest`; accepted `EventKind` schema identity; runtime-provided registry, authority and event ledger protocols.
- Produces: `ComponentKind`, `ComponentStatus`, `EdgeKind`, `InterfaceClass`, `InterfaceStability`, `ArchitectureComponent`, `InterfaceContract`, `ArchitectureEdge`, `ArchitectureRevision`, `ArchitectureGraph`, `ArchitectureControlPlane` from the canonical module.

- [ ] Copy the accepted executable semantics into `nolane.external_core.architecture` without behavior expansion.
- [ ] Change digest dependency to `from nolane.core.canonical_digest import canonical_digest` while retaining the accepted shared `EventKind` identity.
- [ ] Add `COMPONENT_ID = "external.architecture"`, `COMPONENT_VERSION = "0.0.1"`, `MIGRATED_FROM = "cogcoder.organization.architecture"` and explicit `__all__`.
- [ ] Preserve sorted deterministic views, append-only versioning, copy-before-validation atomicity, cycle detection, graph digest, state validation, write authorization, concern emission and persistence semantics byte-for-semantics.
- [ ] Replace the historical module with explicit imports/re-exports of the canonical public objects and no second implementation.
- [ ] Run the Wave 5O focused tests plus `tests/test_coding_agi_architecture_*.py`; require green before metadata cutover.

Representative bridge contract:

```python
from nolane.external_core.architecture import ArchitectureGraph, ArchitectureControlPlane

__all__ = (..., "ArchitectureGraph", "ArchitectureControlPlane")
```

---

### Task 3: Cut component authority and facade bookkeeping

**Files:**
- Modify: `cogcoder/refoundation/component_versions.py`
- Modify: `cogcoder/refoundation/facades.py`
- Modify: `cogcoder/refoundation/implementation_status.py`
- Test: `tests/test_refoundation_wave5o_native_architecture.py`

**Interfaces:**
- Consumes: canonical component manifest set.
- Produces: `external.architecture` version `0.0.1`, `canonical_native` status, canonical write authority, and no active compatibility facade.

- [ ] Add `"external.architecture": 1` to the component revision map and change no unrelated revision.
- [ ] Remove only the `external.architecture` `FacadeBinding` from active facade bindings.
- [ ] Add an `_NATIVE` record mapping `external.architecture` to `nolane.external_core.architecture`, provenance `cogcoder/organization/architecture.py`, and notes that accurately bound the accepted behavior.
- [ ] Run focused ledger/version/facade tests and prior Refoundation component/facade tests.

Expected invariant:

```python
row = build_component_implementation_ledger()["external.architecture"]
assert row.status is ImplementationStatus.CANONICAL_NATIVE
assert row.canonical_write_authority is True
assert row.component_version == "0.0.1"
```

---

### Task 4: Regenerate repository truth from canonical authority

**Files:**
- Generated: `CURRENT/NATIVE_DEBT.json`
- Generated: `CURRENT/NATIVE_DEBT.md`
- Potentially generated only if source truth changes require it: other `nolane.repository.audit` projections.

**Interfaces:**
- Consumes: canonical implementation ledger and repository census.
- Produces: byte-exact generated debt projection with 30 non-native components and no `external.architecture` entry.

- [ ] Run `python -m nolane.repository.audit --write` in a clean executable checkout or accepted temporary-carrier workflow.
- [ ] Confirm only generated outputs expected from the Wave 5O source authority change differ.
- [ ] Remove any temporary carrier from source history before acceptance.
- [ ] Run `python -m nolane.repository.audit --check`; require byte-exact pass.
- [ ] Run Wave 5O debt assertions and prior repository-audit tests.

---

### Task 5: Exact-head acceptance and review evidence

**Files:**
- No production additions beyond Tasks 2–4.
- PR metadata/evidence references only after the source head is final.

**Acceptance commands:**

```bash
python -m compileall -q cogcoder/organization cogcoder/refoundation nolane
python -m nolane.ai.materialize --check
python -m nolane.repository.audit --check
python -m pytest -q tests/test_refoundation_*.py
python -m pytest -q tests/test_coding_agi_architecture_*.py tests/test_coding_agi_integration_*.py
python model/neural-r2.3/scripts/verify_neural_r23.py
```

The repository Refoundation workflow must additionally run the broad organization/campaign/execution regression lane already defined in `.github/workflows/refoundation-epoch0-wave1.yml` on both Python 3.11 and 3.13.

- [ ] Require the exact final commit to have green Refoundation workflow jobs for Python 3.11 and 3.13.
- [ ] Inspect job logs rather than treating workflow presence as success.
- [ ] Confirm 67/67 dossier freshness, repository-audit freshness, all Refoundation tests, Architecture/Integration regressions, broad organization regressions and frozen Neural R2.3 metadata are green.
- [ ] Record exact source SHA and hosted run evidence in the draft PR description.
- [ ] Mark ready for review only after all gates are green; do not auto-merge.

## Plan self-review

- Spec coverage: ownership, canonical dependency, bridge identity, graph semantics, persistence, metadata, generated debt, hosted acceptance and non-goals all map to explicit tasks.
- Placeholder scan: no implementation placeholders or deferred Wave 5O requirements remain.
- Type consistency: public Architecture object names exactly match the accepted Part-IV implementation.
- Scope control: one canonical semantic component is migrated; Integration and adjacent authorities remain explicit later debt.
