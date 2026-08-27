# Wave 5AH Native Evaluation Stress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the `evaluation.stress` compatibility facade by moving long-horizon stress scenario, observation, assessment, and ledger authority into `nolane.evaluation.stress` without behavior loss or reverse legacy imports.

**Architecture:** Preserve the accepted public API and persistence format byte-for-semantic-byte while retargeting the implementation to canonical dependencies only: `nolane.organization.identity.AgentRegistry`, `nolane.external_core.evidence.EvidenceRecord`, and `nolane.core.canonical_digest.canonical_digest`. Reduce `cogcoder.organization.evaluation_stress` to an exact-object historical bridge, mark `evaluation.stress` canonical-native at component version `0.0.1`, then regenerate repository debt projections from the authority ledger.

**Tech Stack:** Python 3.11/3.13, dataclasses, enums, pytest, GitHub Actions, Nolane Refoundation component-version/implementation/facade ledgers.

**Spec:** `CURRENT/STATUS.md` + `CURRENT/NATIVE_DEBT.json`

## Global Constraints

- Preserve every accepted `evaluation.stress` public symbol and exact legacy import identity.
- Preserve existing `to_state` / `from_state`, digest validation, fail-closed verifier checks, subject self-verification rejection, required-scenario assessment behavior, and idempotent record semantics.
- Canonical implementation must not import `cogcoder.organization`.
- Canonical implementation may depend only on already-native authorities required by the current legacy implementation.
- `evaluation.stress` component version becomes exactly `0.0.1`.
- Native debt must decrease monotonically from 16 to 15 records and remove only `evaluation.stress` for this wave.
- CI must check committed audit projections directly; it must never repair them with `nolane.repository.audit --write` before `--check`.
- Python 3.11 and 3.13 acceptance matrices must both pass before Wave 5AH is accepted.

---

### Task 1: Lock the Wave 5AH cutover contract RED

**Files:**
- Create: `tests/test_refoundation_wave5ah_native_evaluation_stress.py`

**Interfaces:**
- Consumes: current `nolane.evaluation.stress`, historical `cogcoder.organization.evaluation_stress`, Refoundation version/facade/implementation ledgers, `AgentRegistry`, and `EvidenceRecord`.
- Produces: a failing contract that specifies canonical ownership, exact historical identity, no reverse legacy imports, stress-suite behavior/round-trip preservation, version/facade/debt retirement, and status receipt.

- [ ] **Step 1: Write the failing ownership and bridge tests**

```python
_PUBLIC_SYMBOLS = (
    "StressScenarioKind",
    "LongHorizonStressObservation",
    "StressSuiteAssessment",
    "LongHorizonStressLedger",
)


def test_wave5ah_canonical_module_owns_evaluation_stress_authority() -> None:
    import nolane.evaluation.stress as canonical
    assert canonical.COMPONENT_ID == "evaluation.stress"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.evaluation_stress"
    for name in _PUBLIC_SYMBOLS:
        assert getattr(canonical, name).__module__ == "nolane.evaluation.stress"


def test_wave5ah_historical_stress_module_bridges_exact_canonical_identity() -> None:
    import cogcoder.organization.evaluation_stress as legacy
    import nolane.evaluation.stress as canonical
    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)
```

- [ ] **Step 2: Add canonical import-boundary and behavior tests**

The behavior fixture creates one permanent verifier identity and clean `EvidenceRecord`, records one clean recovered observation for every `LongHorizonStressLedger.REQUIRED_SCENARIOS` entry under one regime digest, asserts `assess_suite(...).passed`, then round-trips `ledger.to_state()` through `LongHorizonStressLedger.from_state(...)` and requires exact state equality.

- [ ] **Step 3: Add authority/debt/status tests**

Require `ImplementationStatus.CANONICAL_NATIVE`, canonical write authority, component version `0.0.1`, no active facade binding, absence from `CURRENT/NATIVE_DEBT.json`, exactly 15 remaining records, and a Wave 5AH status receipt containing `evaluation.stress` and `15 non-native`.

- [ ] **Step 4: Run CI and verify RED for the intended reasons**

Run: `python -m pytest -q tests/test_refoundation_wave5ah_native_evaluation_stress.py`

Expected before implementation: failures for canonical ownership/version, historical exact identity, native implementation status/facade retirement, debt count, and status receipt. Behavior may already pass through the facade and must not be treated as proof of native ownership.

---

### Task 2: Move stress authority into the canonical package

**Files:**
- Modify: `nolane/evaluation/stress.py`
- Modify: `cogcoder/organization/evaluation_stress.py`

**Interfaces:**
- Consumes: `nolane.organization.identity.AgentRegistry`, `nolane.external_core.evidence.EvidenceRecord`, `nolane.core.canonical_digest.canonical_digest`.
- Produces: canonical `StressScenarioKind`, `LongHorizonStressObservation`, `StressSuiteAssessment`, and `LongHorizonStressLedger`; historical module re-exports those exact objects.

- [ ] **Step 1: Copy the accepted implementation under canonical ownership**

Move the full existing implementation to `nolane/evaluation/stress.py`; change only dependency imports and component metadata:

```python
from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord
from nolane.organization.identity import AgentRegistry

COMPONENT_ID = "evaluation.stress"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.evaluation_stress"
```

Do not alter stress validation, digest payloads, required scenarios, assessment reasons, ordering, persistence shape, or idempotency semantics in this migration.

- [ ] **Step 2: Reduce the historical implementation to an exact bridge**

```python
from nolane.evaluation.stress import *
from nolane.evaluation.stress import (
    LongHorizonStressLedger,
    LongHorizonStressObservation,
    StressScenarioKind,
    StressSuiteAssessment,
)

__all__ = (
    "StressScenarioKind",
    "LongHorizonStressObservation",
    "StressSuiteAssessment",
    "LongHorizonStressLedger",
)
```

- [ ] **Step 3: Run the focused contract**

Run: `python -m pytest -q tests/test_refoundation_wave5ah_native_evaluation_stress.py`

Expected: ownership, identity, import-boundary, and behavior tests pass; authority/debt/status tests remain RED until Task 3.

---

### Task 3: Retire facade/version/debt authority and materialize receipts

**Files:**
- Modify the canonical component-version authority containing `evaluation.stress`.
- Modify the implementation-status authority containing `evaluation.stress`.
- Modify the active-facade authority containing `evaluation.stress`.
- Modify: `CURRENT/NATIVE_DEBT.json`
- Modify: `CURRENT/NATIVE_DEBT.md`
- Modify: `CURRENT/STATUS.md`

**Interfaces:**
- Consumes: canonical stress implementation from Task 2.
- Produces: repository-level proof that `evaluation.stress` is native 0.0.1 and remaining non-native debt is exactly 15.

- [ ] **Step 1: Promote implementation authority**

Set `evaluation.stress` to canonical module `nolane.evaluation.stress`, status `canonical_native`, canonical write authority `true`, component version `0.0.1`, and preserve the historical source only as provenance/bridge metadata.

- [ ] **Step 2: Retire the active facade binding**

Remove only the active facade record for `evaluation.stress`; do not retire unrelated evaluation boundaries.

- [ ] **Step 3: Regenerate audit projections outside CI**

Run: `python -m nolane.repository.audit --write`

Then immediately run: `python -m nolane.repository.audit --check`

Expected: `evaluation.stress` absent, 15 non-native records, and no stale paths.

- [ ] **Step 4: Add the Wave 5AH status receipt**

Document that Wave 5AH retires exactly `evaluation.stress`, preserves `cogcoder.organization.evaluation_stress` as an exact semantic bridge, and reduces generated debt from 16 to 15 while leaving parameters/release/claims/scaling/campaign and External Core/historical/frozen boundaries explicit.

---

### Task 4: Fresh exact-head acceptance

**Files:**
- Verify only; modify files only if a real regression is discovered.

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: merge-ready Wave 5AH evidence.

- [ ] **Step 1: Verify generated authorities before tests**

Run: `python -m nolane.ai.materialize --check`

Run: `python -m nolane.repository.audit --check`

Expected: 67/67 AI dossiers fresh and exactly 15 non-native component records.

- [ ] **Step 2: Run Refoundation contracts**

Run: `python -m pytest -q tests/test_refoundation_*.py`

Expected: all pass on Python 3.11 and 3.13.

- [ ] **Step 3: Run organization/campaign/execution regressions**

Run the same regression selection encoded in `.github/workflows/refoundation-epoch0-wave1.yml`.

Expected: all pass on Python 3.11 and 3.13.

- [ ] **Step 4: Verify frozen Neural R2.3**

Run: `python model/neural-r2.3/scripts/verify_neural_r23.py`

Expected: `Neural R2.3 contracts: PASS`.

- [ ] **Step 5: Accept only the exact final head**

GitHub Actions must run the Refoundation Epoch 0 matrix against the final Wave 5AH PR head. Do not reuse a green run from an earlier head and do not allow CI to run `audit --write` before freshness checks.
