# Goal/Design Revision History Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, typed, tamper-evident public Goal Revision History ledger projected from existing Goal Integrity contract/evolution authority without creating a second mutation authority.

**Architecture:** Create a focused `goal_design_revision_history.py` projection module over the existing immutable contract archive, predecessor topology, evolution receipts, and runtime trust labels. Expose it only through `GoalIntegrityRuntime.goal_revision_history(...)`, which supplies validated current authority and exact schema negotiation. Keep historical Goal Integrity contracts, evolution receipts, and runtime persistence schemas unchanged.

**Tech Stack:** Python 3.11/3.12, frozen dataclasses, enums, deterministic `stable_digest`, existing Goal Integrity evolution protocol, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-02-goal-design-revision-history-ledger-design.md`

## Global Constraints

- Do not mutate historical `GoalIntegrityContract`, `GoalIntegrityEvolutionReceipt`, or runtime-state identities.
- Ledger is read-only projection authority, never mutation/revocation/promotion authority.
- No provider/model/tool/browser/repository calls during projection.
- Legacy state remains explicitly legacy; no fabricated provenance, freshness, confidence, or trust promotion.
- Root entries use `confidence_milli=None` and `uncertainty_milli=1000`.
- Explicit receipted revisions copy source/evidence/freshness/confidence exactly from the accepted receipt.
- Unknown ledger schema versions fail closed; no silent downgrade.
- Per-entry fields and reference collections are bounded.
- Production code follows hosted behavioral RED only.
- Final acceptance requires Goal Design Python 3.11/3.12, Refoundation Python 3.11/3.13, R1.9, R2.0i, latest-main race guard, expected-head protected merge, and actual-main verification.

---

### Task 1: Hosted RED — No Public Goal Revision History Yet

**Files:**
- Create: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- Consumes: existing `GoalIntegrityRuntime`, `GoalIntegrityContract`, verifier-issued evolution receipts.
- Produces required public seam: `GoalIntegrityRuntime.goal_revision_history(goal_id, *, schema_version=1)`.

- [ ] **Step 1: Build a valid verifier-backed two-contract history fixture**

Use `GoalIntegrityRuntime.__new__` plus the same blank-state fields used in `test_goal_design_integrity_evolution_authenticity.py`. Inject a `GoalIntegrityEvolutionAuthorityVerifier`, install a root contract, authorize one exact successor, mint `mint_verified_goal_integrity_evolution_receipt(...)`, then install the successor.

- [ ] **Step 2: Write one behavioral test**

```python
def test_runtime_projects_deterministic_public_goal_revision_history():
    runtime, original, revised, receipt = _runtime_with_verified_revision()
    history = runtime.goal_revision_history(original.goal_id)
    assert history.goal_id == original.goal_id
    assert history.current_contract_digest == revised.digest
    assert tuple(entry.contract_digest for entry in history.entries) == (
        original.digest,
        revised.digest,
    )
    assert history.entries[-1].evolution_receipt_id == receipt.receipt_id
```

- [ ] **Step 3: Push test-only commit and require hosted RED**

Run Goal Design Coherence Plane on Python 3.11/3.12. Expected failure after the fixture successfully installs the verified revision:

`AttributeError: 'GoalIntegrityRuntime' object has no attribute 'goal_revision_history'`

Import/collection errors, fixture authorization failures, or unrelated test failures do not count as RED.

---

### Task 2: Typed Protocol and Immutable History Artifacts

**Files:**
- Create: `nolane/external_core/goal_design_revision_history.py`
- Modify: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- Produces:
  - `GOAL_REVISION_HISTORY_SCHEMA_VERSION`
  - `GoalRevisionEvidenceStatus`
  - `GoalRevisionFreshnessStatus`
  - `GoalRevisionHistoryProtocol`
  - `GoalRevisionHistoryEntry`
  - `GoalRevisionHistoryLedger`
  - `GoalRevisionHistoryProjector`

- [ ] **Step 1: Add bounded canonical helpers**

Implement `_text(...)`, `_refs(...)`, `_confidence(...)`, using limits equivalent to the accepted evolution receipt protocol: text <= 4096, one ref <= 512, <= 64 refs per collection. Reject blank required references and non-finite/unbounded values.

- [ ] **Step 2: Add schema/capability descriptor**

`GoalRevisionHistoryProtocol(schema_version=1)` must expose canonical capabilities:

```python
(
    "bounded_uncertainty",
    "canonical_history",
    "explicit_trust",
    "freshness_state",
    "restart_replay",
    "source_lineage",
    "tamper_evident_identity",
    "transformation_history",
)
```

`digest` binds protocol name, schema, compatible versions, and capabilities.

- [ ] **Step 3: Add typed evidence/freshness enums**

Exact values:

```python
class GoalRevisionEvidenceStatus(str, Enum):
    VERIFIED = "verified"
    LEGACY_UNVERIFIED = "legacy_unverified"
    LEGACY_UNATTESTED = "legacy_unattested"
    ROOT_UNATTESTED = "root_unattested"

class GoalRevisionFreshnessStatus(str, Enum):
    ATTESTED = "attested"
    UNATTESTED = "unattested"
```

- [ ] **Step 4: Add content-addressed entry**

`GoalRevisionHistoryEntry` must canonicalize all IDs/refs, validate sequence >= 0, confidence in `[0,1000]` or None, uncertainty in `[0,1000]`, and derive `entry_id` from every semantic field. Root invariants: no predecessor/delta/receipt/authority/freshness ref, evidence status `ROOT_UNATTESTED`, confidence None, uncertainty 1000.

- [ ] **Step 5: Add content-addressed ledger**

`GoalRevisionHistoryLedger` requires non-empty entries, contiguous sequence from zero, same goal on every entry, exactly one final current entry, final digest equals `current_contract_digest`, and derives `history_digest` from schema/protocol/goal/head/entry IDs/aggregate refs.

- [ ] **Step 6: Run focused value-object tests GREEN**

Run:

`python -m pytest -q tests/test_goal_design_revision_history.py`

Expected: artifact/value-object tests pass; runtime seam test may remain failing until Task 4.

---

### Task 3: Deterministic Authority Projector

**Files:**
- Modify: `nolane/external_core/goal_design_revision_history.py`
- Modify: `tests/test_goal_design_revision_history.py`
- Create: `tests/test_goal_design_revision_history_adversarial.py`

**Interfaces:**
- Produces:

```python
GoalRevisionHistoryProjector.project(
    *,
    goal_id: str,
    contracts: Mapping[str, GoalIntegrityContract],
    current_digest: str,
    predecessors: Mapping[str, str | None],
    evolution_receipts: Mapping[str, GoalIntegrityEvolutionReceipt],
    trust_labels: Mapping[str, str],
) -> GoalRevisionHistoryLedger
```

- [ ] **Step 1: Validate exact one-goal topology**

Filter/projector input must contain only one goal. Validate every contract key equals `contract.digest`, every predecessor key is a known contract, roots are unique, non-root predecessors are known, no self-edge, no branch, no cycle, and all supplied contracts form the one root-to-current chain. Reject disconnected historical contracts instead of silently omitting them.

- [ ] **Step 2: Re-derive each structural delta**

For each non-root edge call `assess_goal_integrity_evolution(predecessor, successor)`. Copy added/removed/changed clause/metric IDs into the entry; `delta_digest` must be the re-derived delta digest, never caller text.

- [ ] **Step 3: Re-verify explicit receipts**

If `successor_digest` is in `evolution_receipts`, call `verify_goal_integrity_evolution_receipt(...)`. Copy exact `receipt_id`, `authority_ref`, `source_refs`, `evidence_refs`, `freshness_ref`, `confidence_milli`, and derive `uncertainty_milli = 1000 - confidence_milli`.

- [ ] **Step 4: Preserve trust provenance exactly**

Map existing runtime trust labels:

- `verified_capability_authority` -> `VERIFIED`, receipt required;
- `legacy_unverified_authority` -> `LEGACY_UNVERIFIED`, receipt required;
- `legacy_unattested` -> `LEGACY_UNATTESTED`, receipt forbidden.

Unknown trust strings fail closed. Root uses projection trust `root_unattested` and receives no non-root trust label input.

- [ ] **Step 5: Project truthful root lineage**

Root `source_refs` are the canonical non-empty `provenance_ref` values from its integrity clauses. Root evidence refs are empty, freshness is `UNATTESTED`, confidence None, uncertainty 1000.

- [ ] **Step 6: Bind transformation history**

For a receipted edge:

```python
transformation_refs = (
    f"predecessor:{predecessor.digest}",
    f"delta:{delta.digest}",
    f"successor:{successor.digest}",
    f"receipt:{receipt.receipt_id}",
)
```

For legacy-unattested edge omit the receipt ref but keep predecessor/delta/successor. Canonical sorting occurs in the entry.

- [ ] **Step 7: Add adversarial topology/trust tests**

Tests must independently cover wrong current head, digest-key rebind, unknown predecessor, branch, cycle, disconnected contract, cross-goal contract, receipt successor mismatch, receipt delta mismatch, verified trust without receipt, legacy-unattested with receipt, unknown trust, and oversized refs.

- [ ] **Step 8: Add deterministic insertion-order test**

Construct semantically identical mappings in opposite insertion order. Require identical `history_digest` and entry IDs.

- [ ] **Step 9: Run projector suites GREEN**

Run:

`python -m pytest -q tests/test_goal_design_revision_history*.py`

---

### Task 4: Strong Public Runtime Seam

**Files:**
- Modify: `nolane/external_core/goal_design_integrity_runtime.py`
- Modify: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- Produces:

```python
GoalIntegrityRuntime.goal_revision_history(
    goal_id: str,
    *,
    schema_version: int = GOAL_REVISION_HISTORY_SCHEMA_VERSION,
) -> GoalRevisionHistoryLedger
```

- [ ] **Step 1: Configure a local projector once**

Add optional `revision_history_projector: GoalRevisionHistoryProjector | None = None` to runtime initialization. If absent instantiate the deterministic default. Do not accept provider/model callbacks.

- [ ] **Step 2: Enforce exact schema negotiation**

Before reading history, require `schema_version == GOAL_REVISION_HISTORY_SCHEMA_VERSION`. Unsupported versions raise `CoherenceError` naming schema/version.

- [ ] **Step 3: Build one-goal validated projection inputs internally**

Call `_ensure_authority_authenticity_state()`. Resolve `_current_contracts[goal_id]`. Select contracts whose `contract.goal_id == goal_id`. Build predecessor mapping only for those exact digests. Select matching evolution receipts. Derive each non-root trust label by calling `self.evolution_trust_label(digest)` rather than trusting a serialized string supplied by the caller.

- [ ] **Step 4: Delegate and translate validation failures**

Wrap projector `ValueError` as `CoherenceError("Goal/Design revision history rejected: ...")`. Unknown goal remains a clear `CoherenceError`/`KeyError` boundary failure. Never return partial entries.

- [ ] **Step 5: Prove no side effects**

Capture `integrity_state()` before and after two history calls. Require state equality and identical history digest.

- [ ] **Step 6: Run runtime + revision-history suites GREEN**

Run:

`python -m pytest -q tests/test_goal_design_revision_history*.py tests/test_goal_design_integrity_runtime*.py`

---

### Task 5: Restart Replay, Legacy Truthfulness, and Tamper Evidence

**Files:**
- Create: `tests/test_goal_design_revision_history_restore.py`
- Modify: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- Validates existing runtime persistence + new projection; introduces no new persistence schema.

- [ ] **Step 1: Verified restart replay test**

Serialize a verifier-backed v3 integrity runtime state. Restore into a blank runtime using an injected verifier that can verify historical authorization proofs. Project history before/after restore. Require identical `history_digest`, entry IDs, trust labels, and current head.

- [ ] **Step 2: Legacy-v2 explicit receipt migration test**

Restore historical v2 state through the existing v3 runtime migration. Require receipted revisions project as `legacy_unverified`, never `verified`.

- [ ] **Step 3: Legacy-v1 unattested migration test**

Restore a historical v1 supersession state. Require the non-root revision to project as `legacy_unattested`, no receipt ID, no authority ref, freshness `unattested`, confidence None, uncertainty 1000.

- [ ] **Step 4: Nested tamper test**

Mutate a serialized evolution receipt, recompute only the public outer runtime digest, and attempt restore. Existing nested verification must reject before history projection can occur.

- [ ] **Step 5: Current-head rewind test**

Rewind serialized `current_contracts` to an old historical digest and recompute outer digest. Existing topology validation must reject; no ledger can be emitted from the tampered runtime.

- [ ] **Step 6: Run restore suites GREEN**

Run:

`python -m pytest -q tests/test_goal_design_revision_history*.py tests/test_goal_design_integrity_evolution*.py tests/test_goal_design_integrity_runtime*.py`

---

### Task 6: Hosted Acceptance, Race Integration, and Closure

**Files:**
- Modify documentation only if production semantics materially differ from the locked spec.

**Interfaces:**
- Produces production-merged revision-history authority plus hosted evidence.

- [ ] **Step 1: Full Goal Design acceptance**

Require `python -m pytest -q tests/test_goal_design*.py` on Python 3.11 and 3.12.

- [ ] **Step 2: Refoundation acceptance**

Require Refoundation Epoch 0 success on Python 3.11 and 3.13 including compile, 67-AI dossier freshness, repository quarantine audit, Refoundation contracts, Truth/Knowledge A contracts, zero-loss evidence, organization/campaign/execution regressions, and frozen Neural R2.3 metadata.

- [ ] **Step 3: Integrity frontier gates**

Require R1.9 and R2.0i SUCCESS. Do not repair unrelated historical frozen-release locks from D.

- [ ] **Step 4: Race guard latest main**

Compare exact accepted head against current `main`. If another specialist advanced main, reject stale evidence. Inspect overlap; preserve concurrent changes byte-for-byte and rebuild an exact union onto latest main, then rerun all required acceptance.

- [ ] **Step 5: Expected-head protected merge**

Merge only the exact hosted-accepted head SHA.

- [ ] **Step 6: Actual-main verification**

Require fresh Goal Design 3.11/3.12 + R1.9 + R2.0i on the actual merge commit. Only then label **Goal Revision History Ledger CLOSED/GREEN**.