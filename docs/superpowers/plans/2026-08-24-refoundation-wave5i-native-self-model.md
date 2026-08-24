# Refoundation Epoch 0 — Wave 5I Native Self-model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Native-cut over `external.self_model` from the historical organization owner to `nolane.external_core.self_model` without behavior loss, while reducing non-native debt from 37 to 36.

**Architecture:** Preserve the complete two-object semantic unit (`SelfModel`, `SelfModelRegistry`) byte-for-semantics in a canonical module that imports only native Identity and Evidence dependencies. Keep the historical module as an exact identity bridge; retire only the Self-model active facade and record explicit native provenance so the pinned historical census still resolves after facade removal.

**Tech Stack:** Python 3.11/3.13, pytest, GitHub Actions, Nolane Refoundation component ledger/versioning/inventory/audit.

**Spec:** `docs/superpowers/specs/2026-08-24-refoundation-wave5i-native-self-model-design.md`

## Global Constraints

- Parent acceptance is exact Wave 5H head `4a260c7957c07a026e9257306ab276ad9c0e2aea`.
- Canonical owner is `nolane.external_core.self_model`.
- Canonical executable dependencies are `nolane.organization.identity.AgentRegistry` and `nolane.external_core.evidence.EvidenceRecord` only.
- Preserve historical behavior; do not invent new learning/calibration/tool/failure/trust/blind-spot semantics.
- Historical `cogcoder.organization.self_model` remains present as an exact bridge; no delete/move.
- Target version is `external.self_model == 0.0.1`.
- Target debt is exactly: compatibility facade 26, legacy internal 2, historical only 7, frozen asset 1, total non-native 36.
- Skills, Knowledge, Context, Individual Evolution, execution, evaluation and Neural authority do not migrate in this wave.
- Temporary write workflows, if used, must be removed before acceptance and covered by cleanup tests.
- Never broad-stage generated Python bytecode; repository hygiene must remain green.
- Never auto-merge.

---

### Task 1: RED contract for complete Self-model ownership

**Files:**
- Create: `tests/test_refoundation_wave5i_native_self_model.py`

**Interfaces:**
- Consumes: historical `SelfModel`, `SelfModelRegistry`, current facade/version/status/inventory APIs.
- Produces: failing architecture contracts plus passing historical behavior parity contract.

- [ ] **Step 1: Add architecture and identity RED assertions**

```python
def test_wave5i_self_model_is_canonical_native_and_versioned():
    row = build_component_implementation_ledger()["external.self_model"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.self_model"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.self_model")) == "0.0.1"
```

Also assert `external.self_model` leaves active facades, while `external.individual_evolution`, `external.context`, and `external.skills` remain facades; both historical classes must be identical to canonical classes and report `__module__ == "nolane.external_core.self_model"`.

- [ ] **Step 2: Add AST reverse-import contract**

Parse the canonical file with `ast` and reject executable imports of:
- `cogcoder.organization.self_model`
- `cogcoder.organization.registry`
- `cogcoder.organization.types`

Do not reject provenance strings such as `MIGRATED_FROM`.

- [ ] **Step 3: Add behavior parity tests**

Use a two-identity registry stub and canonical `EvidenceRecord` to prove:
- initialization and fallback version behavior;
- score/domain validation;
- external clean-evidence requirement;
- sorted domain competence;
- revision advancement;
- evidence-ID deduplication;
- registry version synchronization;
- state round-trip and filling missing models on restore.

- [ ] **Step 4: Add provenance/debt RED assertions**

```python
census = GitSnapshotInventory.capture(ROOT, FIRST_GENERATION_SNAPSHOT).to_census()
assert census.get("cogcoder/organization/self_model.py").canonical_destination == "nolane/external_core/self_model.py"
assert len(non_native) == 36
assert counts == {
    "compatibility_facade": 26,
    "frozen_asset": 1,
    "historical_only": 7,
    "legacy_internal": 2,
}
```

- [ ] **Step 5: Run hosted RED on the Wave 5I branch**

Run the normal `Nolane-AI Refoundation Epoch 0` PR workflow. Expected: historical behavior tests pass; only not-yet-cut-over architecture/version/facade/provenance/debt assertions fail.

### Task 2: Move Self-model implementation authority

**Files:**
- Replace: `nolane/external_core/self_model.py`
- Replace: `cogcoder/organization/self_model.py`
- Test: `tests/test_refoundation_wave5i_native_self_model.py`

**Interfaces:**
- Consumes: `AgentRegistry`, `EvidenceRecord`.
- Produces: canonical `SelfModel` and `SelfModelRegistry` with exact historical bridge identity.

- [ ] **Step 1: Replace canonical facade with native implementation**

Canonical header:

```python
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Any, Mapping

from nolane.external_core.evidence import EvidenceRecord
from nolane.organization.identity import AgentRegistry

COMPONENT_ID = "external.self_model"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.self_model"
```

Move the accepted `SelfModel` and `SelfModelRegistry` implementation without semantic expansion and expose:

```python
__all__ = ["SelfModel", "SelfModelRegistry"]
```

- [ ] **Step 2: Replace historical owner with exact bridge**

```python
from nolane.external_core.self_model import SelfModel, SelfModelRegistry

__all__ = ["SelfModel", "SelfModelRegistry"]
```

- [ ] **Step 3: Run focused behavior/identity contracts**

Run:

```bash
python -m pytest -q tests/test_refoundation_wave5i_native_self_model.py
```

Expected after only implementation move: behavior and identity pass; authority/facade/version/provenance/debt remain RED until Task 3.

### Task 3: Cut over component authority and pinned provenance

**Files:**
- Modify: `cogcoder/refoundation/facades.py`
- Modify: `cogcoder/refoundation/component_versions.py`
- Modify: `cogcoder/refoundation/implementation_status.py`
- Modify: `cogcoder/refoundation/inventory.py`
- Modify: `tests/test_refoundation_component_versions.py`
- Modify: `tests/test_refoundation_implementation_status.py`
- Modify only stale cross-wave tests that explicitly freeze Self-model as facade/version 0.

**Interfaces:**
- Consumes: accepted canonical Self-model owner.
- Produces: native ledger authority, local revision 1, explicit pinned-tree mapping.

- [ ] **Step 1: Remove only the `external.self_model` `FacadeBinding`**

Keep Context, Skills and Individual Evolution bindings unchanged.

- [ ] **Step 2: Advance only Self-model component revision**

Add:

```python
"external.self_model": 1,
```

to the revision-one map and accepted revision-one test set.

- [ ] **Step 3: Register canonical native implementation**

Add `_NATIVE` record:

```python
"external.self_model": (
    "nolane.external_core.self_model",
    ("cogcoder/organization/self_model.py",),
    "Native evidence-gated permanent-agent self-model registry; historical module bridges both public object identities.",
),
```

and add the component to accepted-native tests.

- [ ] **Step 4: Preserve historical source destination after facade retirement**

Add to `_CANONICAL_NATIVE_DESTINATIONS`:

```python
"cogcoder/organization/self_model.py": "nolane/external_core/self_model.py",
```

- [ ] **Step 5: Make older wave assertions forward-compatible only where necessary**

A prior test may assert Self-model is still a facade or version `0.0.0`. Replace only that stale future-freezing assertion with the new accepted invariant; do not weaken unrelated contracts.

- [ ] **Step 6: Run focused contracts**

```bash
python -m pytest -q \
  tests/test_refoundation_wave5i_native_self_model.py \
  tests/test_refoundation_component_versions.py \
  tests/test_refoundation_implementation_status.py \
  tests/test_refoundation_wave5f_repository_hygiene.py
```

Expected: all focused tests pass except generated audit projections if stale.

### Task 4: Regenerate deterministic debt projections

**Files:**
- Generated: `CURRENT/NATIVE_DEBT.json`
- Generated: `CURRENT/NATIVE_DEBT.md`
- Test: `tests/test_refoundation_wave5i_bootstrap_cleanup.py`

**Interfaces:**
- Consumes: implementation ledger with Self-model canonical native.
- Produces: fresh repository audit projection at debt 36.

- [ ] **Step 1: Run audit generator**

```bash
python -m nolane.repository.audit --write
git diff --exit-code -- archive/INDEX.json
python -m nolane.repository.audit --check
```

Expected audit summary: `173 historical root artifacts; 173 quarantined / 0 safe-to-move; 36 non-native component records`.

- [ ] **Step 2: Verify generated scope**

Only the two native-debt projections may change from audit generation. Experience remains native and Self-model disappears from non-native rows.

- [ ] **Step 3: Add cleanup contract**

If any temporary mutation workflow is needed, assert its exact path is absent in the final tree. Include all Wave 5I temporary workflow names in one cleanup test.

### Task 5: Exact clean-head acceptance

**Files:**
- Update PR body only after hosted acceptance.

**Interfaces:**
- Consumes: post-cleanup Wave 5I head.
- Produces: accepted evidence record and Ready-for-Review stacked PR.

- [ ] **Step 1: Remove all temporary mutation workflows**

Verify cleanup contract is present before deleting the carrier workflow.

- [ ] **Step 2: Run exact post-cleanup hosted matrix**

Required workflow: `Nolane-AI Refoundation Epoch 0`, Python 3.11 and 3.13.

Both jobs must succeed through:
- compile;
- 67/67 AI dossier freshness;
- repository audit freshness;
- all Refoundation contracts;
- zero-loss evidence bundle generation/upload;
- all organization/campaign/execution regressions;
- frozen Neural R2.3 metadata contracts.

- [ ] **Step 3: Record artifact evidence**

Capture exact accepted head SHA, run ID, both artifact IDs and SHA-256 digests.

- [ ] **Step 4: Update stacked PR and mark Ready**

PR must remain unmerged. Body records scope, debt delta 37→36, RED evidence, final run evidence, artifact digests and no-delete/no-merge boundaries.