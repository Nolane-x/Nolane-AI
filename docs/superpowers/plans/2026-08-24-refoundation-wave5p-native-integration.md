# Refoundation Epoch 0 Wave 5P — Native Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut `external.integration` over to native canonical implementation ownership while preserving accepted Integration behavior, historical import compatibility, and current repository-authority truth.

**Architecture:** Move the accepted Integration candidate graph/control-plane implementation into `nolane.external_core.integration`, turn the historical module into an exact-object bridge, move canonical digest usage to `nolane.core.canonical_digest`, and update only the component/facade/implementation ledgers required to remove this one native-debt entry. Keep Compatibility/ADR/change-impact ownership out of this wave.

**Tech Stack:** Python 3.11/3.13, standard-library dataclasses/enums, pytest, GitHub Actions, existing Refoundation repository audit.

**Spec:** `docs/superpowers/specs/2026-08-24-refoundation-wave5p-native-integration-design.md`

## Global Constraints

- Base branch is `refoundation/epoch0-wave5o-native-architecture`.
- Preserve exactly 67 permanent first-generation AI identities.
- Preserve historical evidence and import provenance; no destructive history cleanup.
- `external.integration` alone advances from `0.0.0` to `0.0.1`.
- Generated audit truth must come from `nolane.repository.audit`, never hand edits.
- Canonical Integration may not reverse-import `cogcoder.organization.integration`.
- Compatibility/ADR/change-impact, leases, execution, coding, assurance, evaluation and neural semantics are out of scope.
- Hosted acceptance must be exact-head Python 3.11/3.13 green before review readiness.

---

### Task 1: Freeze Wave 5P ownership contracts and prove RED

**Files:**
- Create: `docs/superpowers/specs/2026-08-24-refoundation-wave5p-native-integration-design.md`
- Create: `docs/superpowers/plans/2026-08-24-refoundation-wave5p-native-integration.md`
- Create: `tests/test_refoundation_wave5p_native_integration.py`

**Consumes:** existing `cogcoder.organization.integration`, `nolane.external_core.integration`, canonical Architecture, Refoundation version/facade/implementation ledgers.

**Produces:** executable acceptance contract for canonical ownership, historical identity bridge, unchanged Integration semantics, metadata migration, status synchronization and debt count.

- [ ] Assert all five public Integration objects have `__module__ == "nolane.external_core.integration"` and canonical metadata is `external.integration` / `0.0.1` / historical provenance path.
- [ ] Add AST/source contract rejecting canonical imports of `cogcoder.organization.integration` and requiring canonical digest authority from `nolane.core.canonical_digest`.
- [ ] Assert historical bridge object identity for every public Integration object.
- [ ] Preserve dependency-cycle atomicity, topological order, state round-trip, evidence/stale-architecture/compatibility/dependency/conflict gating, and deterministic receipt semantics.
- [ ] Assert implementation-ledger/facade/version state and generated-debt target 29.
- [ ] Assert `CURRENT/STATUS.md` no longer claims Wave 4 is active and records Wave 5P accurately.
- [ ] Require the pre-production head to fail specifically on the Wave 5P ownership/version/debt contracts before implementation changes.

Expected RED causes on the Wave 5O base:

```text
canonical public classes report cogcoder.organization.integration
COMPONENT_VERSION is 0.0.0
canonical source reverse-imports historical Integration
external.integration remains an active facade
external.integration remains non-native debt (30 total)
CURRENT/STATUS.md still reports Wave 4 active work
```

---

### Task 2: Move accepted Integration implementation to canonical ownership

**Files:**
- Replace: `nolane/external_core/integration.py`
- Replace: `cogcoder/organization/integration.py`
- Test: `tests/test_refoundation_wave5p_native_integration.py`
- Regression: `tests/test_coding_agi_integration_*.py`

**Interfaces:**
- Consumes: `canonical_digest` from `nolane.core.canonical_digest`; accepted Compatibility assessment identities; runtime-provided registry, authority and canonical Architecture control-plane protocols.
- Produces: `ChangeCandidateStatus`, `ChangeCandidate`, `IntegrationReceipt`, `IntegrationGraph`, `IntegrationControlPlane` from the canonical module.

- [ ] Copy accepted executable semantics into `nolane.external_core.integration` without behavior expansion.
- [ ] Change digest dependency to `from nolane.core.canonical_digest import canonical_digest`.
- [ ] Retain accepted `CompatibilityAssessment` / `CompatibilityClass` identity without claiming their ownership.
- [ ] Add `COMPONENT_ID = "external.integration"`, `COMPONENT_VERSION = "0.0.1"`, `MIGRATED_FROM = "cogcoder.organization.integration"`, and explicit `__all__`.
- [ ] Preserve candidate validation, graph mutation/versioning, deterministic ordering, snapshot validation, authority checks, evidence gating, stale-architecture checks, compatibility gating, dependency/conflict gates and receipt digest semantics byte-for-semantics.
- [ ] Replace the historical module with explicit imports/re-exports of canonical public objects and no second implementation.
- [ ] Run focused Wave 5P tests plus `tests/test_coding_agi_integration_*.py` before metadata cutover.

---

### Task 3: Cut component authority and facade bookkeeping

**Files:**
- Modify: `cogcoder/refoundation/component_versions.py`
- Modify: `cogcoder/refoundation/facades.py`
- Modify: `cogcoder/refoundation/implementation_status.py`
- Test: `tests/test_refoundation_wave5p_native_integration.py`

- [ ] Add `"external.integration": 1` to the component revision map and change no unrelated revision.
- [ ] Remove only the `external.integration` active `FacadeBinding`.
- [ ] Add an `_NATIVE` record mapping `external.integration` to `nolane.external_core.integration`, provenance `cogcoder/organization/integration.py`, and notes accurately bounding accepted behavior.
- [ ] Require `canonical_native`, canonical write authority, and component version `0.0.1`.

---

### Task 4: Synchronize current repository authority

**Files:**
- Modify: `CURRENT/STATUS.md`

- [ ] Preserve accepted Wave 1–4 history.
- [ ] Record Wave 5 native-extraction lineage through 5M Requirements, 5N Planning, and 5O Architecture.
- [ ] Record Wave 5P native Integration as active work on this branch.
- [ ] Keep residual native debt explicit rather than implying complete refoundation.
- [ ] Avoid changing repository-precedence semantics owned by `CURRENT/REPOSITORY_AUTHORITY.md`.

---

### Task 5: Regenerate repository truth from canonical authority

**Files:**
- Generated: `CURRENT/NATIVE_DEBT.json`
- Generated: `CURRENT/NATIVE_DEBT.md`
- Potentially generated only if source truth changes require it: other `nolane.repository.audit` projections.

- [ ] Run `python -m nolane.repository.audit --write` in an executable checkout or exact-head CI carrier.
- [ ] Confirm only expected generated outputs differ.
- [ ] Run `python -m nolane.repository.audit --check`; require byte-exact pass.
- [ ] Confirm exactly 29 non-native components remain and `external.integration` is absent.

---

### Task 6: Exact-head acceptance and review evidence

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
- [ ] Record exact source SHA and hosted run evidence before review readiness.
- [ ] Do not auto-merge.

## Plan self-review

- Spec coverage: ownership, canonical dependency, bridge identity, graph semantics, persistence, metadata, generated debt, status synchronization, hosted acceptance and non-goals all map to explicit tasks.
- Placeholder scan: no implementation placeholders or deferred Wave 5P requirements remain.
- Type consistency: public Integration object names exactly match the accepted Part-IV implementation.
- Scope control: one canonical semantic component is migrated; Compatibility/ADR/change-impact and adjacent authorities remain explicit later debt.
