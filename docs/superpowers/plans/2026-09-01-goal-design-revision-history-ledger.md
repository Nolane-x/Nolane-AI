# Goal/Design Revision History Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the already-authenticated Goal Integrity contract evolution chain as a deterministic, typed, restart-verifiable public Goal Revision History ledger without creating new mutation authority.

**Architecture:** Add one focused `goal_design_revision_history.py` projection/compiler module and one read-only `GoalIntegrityRuntime.goal_revision_history(...)` seam. The compiler walks existing immutable contract/predecessor/evolution-receipt state, resolves trust through the runtime's existing provenance classes, and emits a content-addressed entry chain, snapshot and public receipt. Historical Goal Integrity and DecisionReceipt identities remain untouched.

**Tech Stack:** Python 3.11/3.12, frozen dataclasses, enums/constants, deterministic `stable_digest`, existing Goal Integrity evolution/authenticity machinery, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-01-goal-design-revision-history-ledger-design.md`

## Global Constraints

- D Goal/Design only; no Family-A truth, E execution, F coding or release authority.
- History projection is read-only and cannot authorize contract mutation.
- Reuse existing contract archive, predecessor topology, evolution receipts and trust provenance; never duplicate them as a second source of truth.
- Preserve every historical `GoalIntegrityContract`, `GoalIntegrityEvolutionReceipt`, `DecisionReceipt`, integrity-state schema and digest identity.
- Protocol `nolane.goal_revision_history` starts at major 1, minor 0.
- Unsupported major or required minor greater than supported minor fails closed.
- Root/legacy missing freshness/confidence/evidence remains explicitly missing; never fabricate provenance.
- No provider, cloud, model, browser or network dependency.
- Production code follows hosted behavioral RED.
- Final acceptance requires Goal Design 3.11/3.12, Refoundation 3.11/3.13, R1.9, R2.0i, latest-main race guard, expected-head merge and actual-main verification.

---

### Task 1: Hosted RED — Public Revision History Seam Is Missing

**Files:**
- Create: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- Consumes existing `GoalIntegrityRuntime`, `GoalIntegrityEvolutionAuthorityVerifier`, `mint_verified_goal_integrity_evolution_receipt`, `GoalIntegrityContract`.
- Requires new public method `GoalIntegrityRuntime.goal_revision_history(goal_id, *, protocol_major=1, minimum_minor=0)`.

- [ ] **Step 1: Build a verifier-backed root -> revision fixture**

Use the same authority fixture pattern as `tests/test_goal_design_integrity_evolution_authenticity.py`: trusted root issuer, root grant, exact transition proof, verified evolution receipt, blank integrity runtime, root install, authorized revision install.

- [ ] **Step 2: Write one behavioral RED**

```python
def test_runtime_exports_typed_verified_goal_revision_history():
    runtime, original, revised, receipt = _verified_revision_runtime()
    history = runtime.goal_revision_history(original.goal_id)
    assert history.snapshot.current_contract_digest == revised.digest
    assert tuple(entry.contract_digest for entry in history.snapshot.entries) == (
        original.digest,
        revised.digest,
    )
    assert history.snapshot.entries[1].evolution_receipt_id == receipt.receipt_id
    assert history.receipt.receipt_id
```

- [ ] **Step 3: Push test-only commit and require hosted RED**

Run hosted Goal Design matrix. Expected failure after successful fixture setup: `AttributeError: 'GoalIntegrityRuntime' object has no attribute 'goal_revision_history'`. Import/collection errors do not count.

---

### Task 2: Typed Protocol, Entry Chain and Receipt Verifier

**Files:**
- Create: `nolane/external_core/goal_design_revision_history.py`
- Modify: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- Produces constants `GOAL_REVISION_HISTORY_PROTOCOL`, `GOAL_REVISION_HISTORY_MAJOR`, `GOAL_REVISION_HISTORY_MINOR`, `ROOT_INTEGRITY_CONTRACT_TRUST`.
- Produces `GoalRevisionHistoryCapability`, `GoalRevisionHistoryEntry`, `GoalRevisionHistorySnapshot`, `GoalRevisionHistoryReceipt`, `GoalRevisionHistoryExport`, `GoalRevisionHistoryCompiler`, `verify_goal_revision_history_export`.

- [ ] **Step 1: Add bounded canonical helpers**

Use local `_text`, `_optional_text`, `_refs` and bounded integer validation. Text max 4096, reference max 512, canonical reference count max 64 per entry, history entries max 4096. Canonicalize set-semantic refs by sorted unique values.

- [ ] **Step 2: Implement protocol capability**

```python
@dataclass(frozen=True)
class GoalRevisionHistoryCapability:
    protocol_name: str = GOAL_REVISION_HISTORY_PROTOCOL
    major: int = GOAL_REVISION_HISTORY_MAJOR
    minor: int = GOAL_REVISION_HISTORY_MINOR
    features: tuple[str, ...] = (...)
    digest: str = field(init=False)
```

Normalize/sort features and derive `digest` from all public capability fields.

- [ ] **Step 3: Implement immutable history entry**

`GoalRevisionHistoryEntry` validates ordinal >= 0, `confidence_milli` is None or 0..1000, root/non-root predecessor/previous-entry shape, bounded refs, then derives `entry_digest` from every semantic field except itself.

- [ ] **Step 4: Implement snapshot and public receipt**

Snapshot validates one goal, contiguous ordinals, root at 0, exact previous-entry digest chain, final entry equals `current_contract_digest`, then derives `history_digest`. Receipt binds protocol major/minor, goal, history digest, current head and entry count; derive `receipt_id` deterministically.

- [ ] **Step 5: Implement stateless export verification**

`verify_goal_revision_history_export(export)` rebuilds/validates entry identities, chain, snapshot history digest, current-head binding and receipt identity. It returns the verified snapshot or raises `ValueError`.

- [ ] **Step 6: Run focused value-type tests GREEN**

Run `python -m pytest -q tests/test_goal_design_revision_history.py` once runtime wiring exists in Task 4; pure-type tests may be run directly earlier.

---

### Task 3: Deterministic Projection Compiler

**Files:**
- Modify: `nolane/external_core/goal_design_revision_history.py`
- Modify: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- `GoalRevisionHistoryCompiler.compile(*, goal_id, current_contract_digest, contracts, predecessors, evolution_receipts, trust_label_resolver, protocol_major=1, minimum_minor=0) -> GoalRevisionHistoryExport`.

- [ ] **Step 1: Implement capability negotiation**

Reject `protocol_major != 1`, negative minimum minor, or `minimum_minor > 0`. Return the canonical v1.0 capability for supported requests.

- [ ] **Step 2: Derive chain strictly from topology**

Starting at current head, follow `predecessors[digest]` until the unique root (`None`), detecting unknown digests, repeated digests/cycles, cross-goal contracts and >4096 entries. Reverse the collected chain to root -> current order. Ignore dictionary insertion order.

- [ ] **Step 3: Project root truthfully**

Root entry uses trust `root_integrity_contract`, no evolution receipt/delta/freshness/confidence, source refs only from actual clause provenance refs, evidence refs only if the contract format actually supplies them, and transformation history `("goal_integrity_contract:v1", "goal_revision_history_projection:v1")`.

- [ ] **Step 4: Project explicit revision receipt**

For a non-root successor with a receipt, call `verify_goal_integrity_evolution_receipt(receipt, predecessor=..., successor=...)`. Copy exact source/evidence/freshness/confidence fields, use the re-derived delta digest, and resolve trust with `trust_label_resolver(successor.digest)`.

- [ ] **Step 5: Project legacy unattested revision without fabrication**

If there is no explicit receipt, require trust resolver to return exactly `legacy_unattested`; emit no receipt/delta/freshness/confidence and no invented source/evidence. Contract provenance may remain represented only as deterministic contract provenance, not as evolution evidence.

- [ ] **Step 6: Reject trust/receipt contradictions**

Explicit receipt + `legacy_unattested` is invalid. Receiptless revision + verified/legacy-unverified trust is invalid. Trust resolver failure is fail-closed.

- [ ] **Step 7: Mint and self-verify export**

Construct entries with exact previous-entry digest links, snapshot, receipt and `GoalRevisionHistoryExport`; call `verify_goal_revision_history_export` before returning.

---

### Task 4: Runtime Read-Only Authority Seam

**Files:**
- Modify: `nolane/external_core/goal_design_integrity_runtime.py`
- Modify: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- Constructor accepts optional `goal_revision_history_compiler: GoalRevisionHistoryCompiler | None = None`.
- Public method `goal_revision_history(goal_id: str, *, protocol_major: int = 1, minimum_minor: int = 0) -> GoalRevisionHistoryExport`.

- [ ] **Step 1: Configure one compiler per runtime**

Type-check optional compiler; after `super().__init__`, set `self.goal_revision_history_compiler = supplied or GoalRevisionHistoryCompiler()`. `_ensure_authority_authenticity_state()` installs a default compiler for historical/unpickled objects without changing serialized integrity schema.

- [ ] **Step 2: Add public history export seam**

Require a nonblank goal and current contract. Pass `dict(self._integrity_contracts)`, `dict(self._contract_predecessors)`, `dict(self._evolution_receipts)` and `self.evolution_trust_label` to the compiler. Catch `ValueError`/`KeyError` and raise `CoherenceError("Goal/Design revision history export rejected: ...")`.

- [ ] **Step 3: Export symbols**

Add the public history types/compiler to `goal_design_integrity_runtime.__all__` without changing historical compatibility modules.

- [ ] **Step 4: Prove no side effects**

Capture `integrity_state()`, current contract, authority records and verifier state before export; assert all remain identical afterward.

---

### Task 5: Adversarial Determinism, Legacy and Restart Coverage

**Files:**
- Modify: `tests/test_goal_design_revision_history.py`

**Interfaces:**
- Validates NC02 contract/determinism/evidence/failure/local-first invariants at the public seam.

- [ ] **Step 1: Root-only export**

Install only root; assert one ordinal-0 entry, root trust, None receipt/delta/freshness/confidence, deterministic receipt ID.

- [ ] **Step 2: Exact verified evidence projection**

Assert revision entry source/evidence/freshness/confidence equal the existing evolution receipt exactly and trust equals `verified_capability_authority`.

- [ ] **Step 3: Determinism under mapping reordering**

Compile from equivalent reversed/rebuilt mappings and assert identical entry digests, history digest and receipt ID.

- [ ] **Step 4: Multi-revision topology ordering**

Install A -> B -> C, scramble mapping insertion order in direct compiler fixture, assert A/B/C ordinals and hash chain.

- [ ] **Step 5: Capability attacks**

Assert major 0/2 and minimum minor 1 reject; major 1/minimum minor 0 succeeds.

- [ ] **Step 6: Receipt/topology attacks**

Direct compiler tests for unknown current digest, missing predecessor, cycle, foreign-goal contract, wrong explicit receipt and current-head rewind all fail before export.

- [ ] **Step 7: Trust laundering attacks**

Assert explicit receipt cannot be labeled legacy-unattested; receiptless legacy cannot become verified; caller has no public parameter to supply trust/source/evidence fields.

- [ ] **Step 8: Legacy migration truthfulness**

Restore historical v1/v2 integrity states using existing runtime migration fixtures. Export and assert `legacy_unattested` has None freshness/confidence and no fabricated evolution evidence; historical v2 explicit receipt becomes `legacy_unverified_authority` with its exact receipt metadata.

- [ ] **Step 9: Restart identity**

For a v3 verified revision, serialize `integrity_state()`, restore into a fresh runtime with the same authority verifier/checkpoint rules, export again and assert identical history digest/receipt ID.

- [ ] **Step 10: Malformed restore cannot be laundered**

Tamper persisted topology/receipt/current pointer and prove existing restore fails; no history export is produced. If live internal mappings are deliberately corrupted in a direct forensic fixture, `goal_revision_history` fails without mutating the prior contract archive.

- [ ] **Step 11: Local-first proof**

No test monkeypatches or calls a provider/network/model. Inspect module imports to keep standard-library + existing local Goal/Design modules only.

---

### Task 6: Hosted Acceptance, Race Integration and Closure

**Files:**
- Modify docs only if implementation semantics changed from the spec.

**Interfaces:**
- Produces accepted mainline Goal Revision History authority.

- [ ] **Step 1: Full Goal Design acceptance**

Hosted `python -m pytest -q tests/test_goal_design*.py` on Python 3.11 and 3.12. Both must succeed.

- [ ] **Step 2: Refoundation acceptance**

Require Python 3.11 and 3.13 success for compile, 67 dossier freshness, quarantine audit, Refoundation contracts, Truth/Knowledge A, zero-loss evidence, organization/campaign/execution regressions and Neural R2.3.

- [ ] **Step 3: Integrity gates**

Require fresh R1.9 and R2.0i SUCCESS. Do not repair unrelated frozen historical release locks from D.

- [ ] **Step 4: Latest-main race guard**

Compare exact branch base/head to current `main`. If main advanced with no D overlap, rebuild an exact union preserving concurrent specialist blobs byte-for-byte and rerun acceptance. If D overlap exists, inspect semantics rather than overwriting.

- [ ] **Step 5: Expected-head protected merge**

Merge only the accepted head SHA.

- [ ] **Step 6: Actual-main verification**

Require actual merge tree to match accepted synthetic semantics, then fresh main Goal Design 3.11/3.12, R1.9 and R2.0i SUCCESS. Only then label **Goal Revision History Ledger CLOSED/GREEN**.