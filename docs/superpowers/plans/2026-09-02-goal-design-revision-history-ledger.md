# Goal/Design Revision History Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, restart-verifiable, read-only public revision-history ledger over Goal Integrity contract evolution without creating new mutation authority.

**Architecture:** Introduce `goal_design_revision_history.py` as a pure projection layer over the accepted Goal Integrity runtime. `GoalIntegrityRuntime.goal_revision_history(...)` delegates to the projector, which walks exact predecessor topology, re-verifies evolution receipts, preserves trust provenance without strengthening it, and emits content-addressed typed records/ledger artifacts.

**Tech Stack:** Python 3.11/3.12, frozen dataclasses, enums, deterministic `stable_digest`, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-02-goal-design-revision-history-ledger-design.md`

## Global Constraints

- Preserve all historical Goal Integrity contract, evolution receipt, runtime-state, and DecisionReceipt identities.
- The ledger is read-only projection authority, never mutation/capability authority.
- No provider, model, clock, network, repository, browser, or secret access participates in projection.
- Legacy provenance must remain explicitly weaker; never synthesize missing evidence/freshness/confidence.
- Projection must fail closed before returning a ledger and must not mutate runtime state.
- Production code follows a hosted behavioral RED.
- Final acceptance requires Goal Design Python 3.11/3.12, Refoundation Python 3.11/3.13, R1.9, R2.0i, race guard, expected-head merge, and actual-main verification.

---

### Task 1: Hosted RED — No Public Revision History Ledger

**Files:**
- Create: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- Consumes existing `GoalIntegrityRuntime`, `GoalIntegrityEvolutionAuthorityVerifier`, `mint_verified_goal_integrity_evolution_receipt`, and Goal Integrity contract types.
- Produces required public seam `GoalIntegrityRuntime.goal_revision_history(goal_id)`.

- [ ] **Step 1: Build a real verified transition fixture**

Create a blank runtime using the same accepted test pattern as `test_goal_design_integrity_evolution_authenticity.py`: initialize integrity dictionaries/index, inject a verifier, install a root contract, issue a root grant, authorize one exact transition, mint a verified evolution receipt, and install the successor.

- [ ] **Step 2: Write the behavioral failing test**

```python
def test_runtime_exposes_deterministic_verified_goal_revision_history():
    runtime, original, revised, receipt = _runtime_with_verified_revision()
    ledger = runtime.goal_revision_history(original.goal_id)
    assert ledger.goal_id == original.goal_id
    assert ledger.current_contract_digest == revised.digest
    assert [record.contract_digest for record in ledger.records] == [original.digest, revised.digest]
    assert ledger.records[1].evolution_receipt_id == receipt.receipt_id
```

- [ ] **Step 3: Push test-only commit and inspect hosted Goal Design workflow**

Expected RED: `AttributeError: 'GoalIntegrityRuntime' object has no attribute 'goal_revision_history'` after root and verified successor installation succeeds. Import/collection failures do not count.

---

### Task 2: Typed Content-Addressed Revision Records

**Files:**
- Create: `nolane/external_core/goal_design_revision_history.py`
- Modify: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- Produces `GoalRevisionTrust`, `GoalRevisionRecord`, `GoalRevisionHistoryLedger`, `GoalRevisionHistoryProjector`.

- [ ] **Step 1: Add typed public trust labels**

Define:

```python
class GoalRevisionTrust(str, Enum):
    ROOT_CONTRACT = "root_contract"
    VERIFIED_CAPABILITY_AUTHORITY = "verified_capability_authority"
    LEGACY_UNVERIFIED_AUTHORITY = "legacy_unverified_authority"
    LEGACY_UNATTESTED = "legacy_unattested"
```

- [ ] **Step 2: Add immutable `GoalRevisionRecord`**

The record stores schema version, goal ID, ordinal, contract/predecessor digests, trust, optional receipt/delta/freshness/confidence, canonical source/evidence/transformation refs, current-head bit, and derived `record_id`.

Validation rules:
- ordinal is non-negative;
- confidence is `None` or integer 0..1000;
- root has no predecessor/receipt/delta/freshness/confidence/transformation refs;
- non-root verified/legacy-unverified entries require receipt/delta/source/evidence/freshness/confidence;
- legacy-unattested entries require predecessor but must not claim receipt/evidence/freshness/confidence.

- [ ] **Step 3: Add immutable `GoalRevisionHistoryLedger`**

Require at least one record, one root at ordinal zero, contiguous ordinals, exact same goal, last record current, all earlier records not current, and current digest equal last record contract digest. Derive `ledger_id` from exact semantic fields plus `runtime_state_digest`.

- [ ] **Step 4: Run focused value-type tests**

Run:
`python -m pytest -q tests/test_goal_design_revision_history.py`

Expected at this checkpoint: value-type tests pass; runtime seam test still fails because projector/runtime method is not implemented yet.

---

### Task 3: Exact Topology Projection and Receipt Re-Verification

**Files:**
- Modify: `nolane/external_core/goal_design_revision_history.py`
- Modify: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- Produces `GoalRevisionHistoryProjector.project(runtime, goal_id) -> GoalRevisionHistoryLedger`.

- [ ] **Step 1: Snapshot runtime state before projection**

Call `runtime.integrity_state()` and bind the ledger to its exact `state_digest`. Do not access clocks or live provider state.

- [ ] **Step 2: Resolve exact root-to-head chain**

Using the runtime's already-validated contract archive/current/predecessor map, construct the requested goal's chain from current head backwards to the unique root, then reverse it. Fail closed for unknown goal, missing contract, cross-goal predecessor, cycle, disconnected current head, or duplicate topology.

- [ ] **Step 3: Re-verify explicit revisions**

For every successor digest present in `_evolution_receipts`, call `verify_goal_integrity_evolution_receipt(receipt, predecessor=..., successor=...)`, preserve exact source/evidence/freshness/confidence fields, and bind `delta.digest` + receipt ID as transformation refs.

- [ ] **Step 4: Map trust without promotion**

Root -> `ROOT_CONTRACT`.
For non-root entries call `runtime.evolution_trust_label(successor_digest)` and map only the three accepted runtime labels. Unknown labels fail closed.

Legacy-unattested records carry only topology + trust and empty provenance fields.

- [ ] **Step 5: Prove exact verified history**

The initial RED test must now pass and assert exact receipt/delta/source/evidence/freshness/confidence preservation.

---

### Task 4: Runtime Public Seam and Failure Atomicity

**Files:**
- Modify: `nolane/external_core/goal_design_integrity_runtime.py`
- Modify: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- Produces `GoalIntegrityRuntime.goal_revision_history(goal_id: str) -> GoalRevisionHistoryLedger`.

- [ ] **Step 1: Add one configured pure projector**

Extend runtime constructor with optional `revision_history_projector`. Validate its type. If absent, instantiate `GoalRevisionHistoryProjector()` once. Backward-compatible blank-runtime test objects must lazily receive the default projector in `_ensure_authority_authenticity_state()`.

- [ ] **Step 2: Add public read-only method**

```python
def goal_revision_history(self, goal_id: str) -> GoalRevisionHistoryLedger:
    self._ensure_authority_authenticity_state()
    try:
        return self.revision_history_projector.project(self, goal_id)
    except ValueError as exc:
        raise CoherenceError(f"Goal/Design revision history rejected: {exc}") from exc
```

No runtime dictionary is modified.

- [ ] **Step 3: Prove side-effect freedom**

Capture `integrity_state()` before/after projection and assert exact equality.

- [ ] **Step 4: Prove unknown-goal failure**

`runtime.goal_revision_history("goal:unknown")` must raise `CoherenceError` and leave state unchanged.

---

### Task 5: Legacy Truthfulness and Restart Verification

**Files:**
- Create: `tests/test_goal_design_revision_history_compatibility.py`

**Interfaces:**
- Validates v1/v2/v3 runtime migration behavior and restart-stable ledger identity.

- [ ] **Step 1: Verified v3 roundtrip**

Persist runtime `integrity_state()`, restore into a fresh runtime with the same verifier authority, re-project, and assert identical `ledger_id`, record IDs, trust, and provenance fields.

- [ ] **Step 2: Legacy-unverified v2 migration**

Restore a historical v2 state containing explicit evolution receipt(s). Assert projected trust is `LEGACY_UNVERIFIED_AUTHORITY` and original receipt source/evidence/freshness/confidence is preserved without calling it verified capability authority.

- [ ] **Step 3: Legacy-unattested v1 migration**

Restore a historical v1 revision chain. Assert non-root trust is `LEGACY_UNATTESTED` and receipt/delta/source/evidence/freshness/confidence are all absent/empty.

- [ ] **Step 4: Root truthfulness**

Root record must never contain fabricated evolution provenance in any schema path.

---

### Task 6: Adversarial Tamper and Determinism

**Files:**
- Create: `tests/test_goal_design_revision_history_adversarial.py`

**Interfaces:**
- Validates fail-closed topology, evidence, identity, and deterministic semantics.

- [ ] **Step 1: Receipt rebind attack**

Mutate a stored receipt's successor/delta/receipt ID through a test-only copied runtime object. Expected: projection fails before returning a ledger.

- [ ] **Step 2: Trust-class laundering attack**

Place one successor in conflicting legacy/verified provenance classes. Expected: projection rejects instead of choosing the stronger class.

- [ ] **Step 3: Topology attacks**

Test self predecessor, unknown predecessor, cross-goal predecessor, and current-head rewind. Every case fails closed.

- [ ] **Step 4: Determinism under dictionary insertion reordering**

Create semantically identical copied runtime state with contract/predecessor/receipt dictionaries inserted in different order. Expected identical `ledger_id` and ordered record IDs.

- [ ] **Step 5: No secret serialization**

Assert serialized/public dataclass fields and `repr(ledger)` contain no authority key material and no verifier object.

---

### Task 7: Acceptance, Race Integration, and Production Closure

**Files:**
- Modify docs only if implementation semantics differ from the accepted spec.

**Interfaces:**
- Produces merged Goal Revision History authority and hosted evidence.

- [ ] **Step 1: Full Goal Design acceptance**

Hosted workflow: `python -m pytest -q tests/test_goal_design*.py` on Python 3.11 and 3.12. Both must pass.

- [ ] **Step 2: Refoundation Epoch 0**

Require Python 3.11 and 3.13 success across compile, 67-AI dossier freshness, repository quarantine audit, Refoundation contracts, Truth Knowledge A, zero-loss evidence, organization/campaign/execution regressions, and frozen Neural R2.3 metadata.

- [ ] **Step 3: Require R1.9 and R2.0i SUCCESS**

Historical frozen release-lock failures outside the D payload remain specialist-owned unless new evidence ties them to this change.

- [ ] **Step 4: Race guard latest `main`**

If another specialist advances main, reject stale evidence, compare drift, preserve concurrent files byte-for-byte, rebuild an exact union, and rerun fresh acceptance.

- [ ] **Step 5: Expected-head protected merge**

Merge only the fully accepted exact head SHA.

- [ ] **Step 6: Actual-main verification**

Require fresh Goal Design 3.11/3.12 + R1.9 + R2.0i on the actual merge commit before labeling **Goal Revision History Ledger CLOSED/GREEN**.
