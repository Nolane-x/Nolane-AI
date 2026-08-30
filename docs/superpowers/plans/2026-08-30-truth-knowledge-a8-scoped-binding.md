# A8 Dependency-Scoped Truth Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace A7's overly broad whole-ledger invalidation for canonical live Truth closure with a content-addressed dependency scope that preserves all relevant ancestor, contradiction, evidence, debt, provenance, negative-verification, and live-revalidation guarantees.

**Architecture:** Extend the existing Truth helpers without creating new canonical authorities. `KnowledgeLedger` derives target lineage/fixed-point scope membership, `EpistemicJudge` derives `TruthDependencyScope`, Verification supports additive scoped receipts/coverage, and `TruthAssuranceGate.close_live()` issues v2 scope-bound certificates while v1 snapshot issuance/restore remain compatible.

**Tech Stack:** Python 3.11/3.13, dataclasses, canonical JSON digest authority, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-30-truth-knowledge-a8-scoped-binding-design.md`

## Global Constraints

- Preserve exactly five canonical External Core A authorities.
- Do not add `COMPONENT_ID` to Truth helper modules.
- Preserve byte-semantic v1 serialized receipt/certificate payloads and digests.
- V2 scoped identities must exclude unrelated whole-ledger digests.
- Scope membership must be recomputed from live canonical ledgers; caller-provided scope is never authority.
- Keep existing risk diversity policy unchanged: LOW/STANDARD 1 source+1 channel, HIGH 2+2, CRITICAL 3+3.
- Every change follows RED -> GREEN -> regression verification.
- Historical Refoundation workflow-isolation rules remain intact.

---

### Task 1: Add A8 RED contracts

**Files:**
- Create: `tests/test_truth_knowledge_hardening_wave8.py`

**Interfaces:**
- Consumes: existing `KnowledgeLedger`, `EpistemicJudge`, `TruthVerificationLedger`, `TruthAssuranceGate`.
- Produces: executable specification for `TruthDependencyScope`, scoped verification receipts, v2 live closure, and ancestor-conflict propagation.

- [ ] **Step 1: Write RED tests for unrelated-state stability**

Create helpers that issue a HIGH-risk target with two independent evidence/verifier channels, then assert a new API `gate.close_live(...)` returns a scoped certificate whose validation survives an unrelated claim+evidence append and an unrelated verification receipt append.

- [ ] **Step 2: Write RED tests for relevant invalidation**

Add tests proving target evidence revocation, ancestor evidence revocation, supported target competitor, supported ancestor competitor, and a new negative target scoped receipt all invalidate or block v2 closure.

- [ ] **Step 3: Write RED tests for canonical scope integrity**

Assert a new `EpistemicJudge().dependency_scope(target_claim_id, knowledge=..., evidence=...)` exposes deterministic lineage/scope IDs; insertion-order permutations produce equal scope digests; different dependency graphs differ; forged/omitted serialized state fails live equality.

- [ ] **Step 4: Run A8 tests on baseline**

Run: `python -m pytest -q tests/test_truth_knowledge_hardening_wave8.py`

Expected: failures because scoped APIs/types do not exist and current `close_live()` certificates stale after unrelated ledger mutations.

- [ ] **Step 5: Commit RED proof**

Commit message: `test: define A8 dependency-scoped truth contracts`

### Task 2: Add canonical Knowledge dependency-closure primitives

**Files:**
- Modify: `nolane/external_core/knowledge_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave8.py`

**Interfaces:**
- Produces: `KnowledgeLedger.lineage_claim_ids(claim_id: str) -> tuple[str, ...]`
- Produces: `KnowledgeLedger.truth_scope_claim_ids(claim_id: str) -> tuple[str, ...]`
- Produces: `KnowledgeLedger.scoped_state(claim_ids: tuple[str, ...]) -> dict[str, Any]`
- Produces: `KnowledgeLedger.scoped_digest(claim_ids: tuple[str, ...]) -> str`

- [ ] **Step 1: Implement lineage fixed point**

Traverse `parent_claim_ids` from the target and return sorted unique target+ancestor IDs. Unknown target/parent remains fail-closed through existing ledger invariants.

- [ ] **Step 2: Implement conflict-neighborhood fixed point**

Repeatedly add all claims sharing `(subject, relation)` with any scoped claim, then add their transitive parents, until stable. Return sorted unique IDs.

- [ ] **Step 3: Implement scoped Knowledge projection**

Serialize only exact `KnowledgeClaim.to_state()` rows for requested canonical claim IDs under an explicit scoped projection schema and hash it with `canonical_digest`.

- [ ] **Step 4: Run Knowledge-focused A8 tests**

Expected: lineage/scope membership, order independence, and graph-identity tests pass; verification/assurance tests still fail.

- [ ] **Step 5: Commit**

Commit message: `feat: derive canonical truth dependency closure`

### Task 3: Add scoped Evidence projection and TruthDependencyScope

**Files:**
- Modify: `nolane/external_core/evidence_truth.py`
- Modify: `nolane/external_core/epistemic_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave8.py`

**Interfaces:**
- Produces: `EvidenceLedger.scoped_state(evidence_ids: tuple[str, ...]) -> dict[str, Any]`
- Produces: `EvidenceLedger.scoped_digest(evidence_ids: tuple[str, ...]) -> str`
- Produces: `TruthDependencyScope`
- Produces: `EpistemicJudge.dependency_scope(claim_id: str, *, knowledge: KnowledgeLedger, evidence: EvidenceLedger) -> TruthDependencyScope`

- [ ] **Step 1: Implement exact Evidence scoped projection**

For every referenced evidence ID emit a canonical row with `missing`, `active`, or `revoked` status. Active/revoked rows include exact evidence state; revoked rows also include the exact revocation row. Sort IDs before hashing.

- [ ] **Step 2: Implement `TruthDependencyScope` dataclass**

Fields: schema, target claim ID, lineage IDs, scope IDs, referenced evidence IDs, scoped Knowledge digest, scoped Evidence digest, scoped assessment rows/digests, scoped contradiction rows/digests, scoped debt rows/digests, and final digest. Constructors reject duplicate/non-canonical identity sets and `from_state()` rechecks content identity.

- [ ] **Step 3: Derive scope from canonical live state**

Use `KnowledgeLedger.truth_scope_claim_ids()`, collect referenced evidence IDs, compute the normal canonical epistemic snapshot once, then filter assessments/contradictions/debts to the scope. Compute final scope digest only from scoped projections.

- [ ] **Step 4: Add live scope validation helper**

`EpistemicJudge.validate_dependency_scope(scope, *, knowledge, evidence) -> bool` recomputes from live state and requires exact equality.

- [ ] **Step 5: Run A8 scope tests and all A1–A7 tests**

Run: `python -m pytest -q tests/test_truth_knowledge_*.py`

Expected: scope tests green; scoped verification/assurance tests remain the only RED surface.

- [ ] **Step 6: Commit**

Commit message: `feat: add canonical dependency-scoped epistemic state`

### Task 4: Add additive scoped Verification binding

**Files:**
- Modify: `nolane/external_core/verification_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave8.py`

**Interfaces:**
- Extend: `TruthVerificationReceipt.create(..., scope_digest: str | None = None)` while preserving v1 behavior when omitted.
- Produces: `TruthVerificationReceipt.is_scoped`
- Produces: `TruthVerificationLedger.scoped_receipts(claim_id: str, *, scope_digest: str)`
- Produces: `TruthVerificationLedger.coverage_scoped(claim_id: str, *, scope_digest: str, evidence: EvidenceLedger)`
- Produces: `TruthVerificationLedger.scoped_digest(claim_id: str, *, scope_digest: str)`

- [ ] **Step 1: Preserve v1 payload exactly**

Do not add new keys to legacy receipt payloads. `from_state()` detects legacy rows by absence of scoped binding fields and reproduces the exact old digest.

- [ ] **Step 2: Add scoped receipt payload**

A v2 receipt contains explicit scoped binding mode + `scope_digest` and excludes whole-ledger Knowledge/Epistemic digests from v2 identity. Mixed-mode rows are rejected.

- [ ] **Step 3: Add scoped lookup/coverage**

Reuse the existing provenance validator. Only receipts for the exact target/current scope count. Negative current-scope receipts remain retained and visible.

- [ ] **Step 4: Add scoped verification projection digest**

Hash only current-scope receipts for the target under a dedicated projection schema. Unrelated claim receipts and stale-scope receipts must not change it.

- [ ] **Step 5: Run verification A8 tests + A1–A7 regression**

Expected: receipt compatibility and unrelated-verification stability tests green; Assurance v2 tests still RED.

- [ ] **Step 6: Commit**

Commit message: `feat: bind verification to dependency scopes`

### Task 5: Add scoped Assurance certificate issuance and validation

**Files:**
- Modify: `nolane/external_core/assurance_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave8.py`

**Interfaces:**
- Extend: `TruthClosureCertificate` with conditional v2 scoped serialization while keeping v1 payload exact.
- Change canonical behavior: `TruthAssuranceGate.close_live()` issues v2 scoped certificates.
- Preserve: `TruthAssuranceGate.close_snapshot()` as v1 global compatibility issuance.
- Extend: `TruthAssuranceGate.validate_certificate()` dispatch by binding mode.

- [ ] **Step 1: Add conditional certificate serialization**

V1 `create/from_state/payload` remains exactly old. V2 requires scoped binding mode, `scope_digest`, scoped verification digest and no global-state binding in its identity. Reject mixed/ambiguous states.

- [ ] **Step 2: Implement v2 strict verification**

Use `coverage_scoped()` and unchanged risk diversity requirements. Any relevant negative current-scope receipt blocks closure.

- [ ] **Step 3: Implement ancestor conflict/debt veto**

Use `TruthDependencyScope.lineage_claim_ids`. Any canonical contradiction containing a lineage claim adds `epistemic_lineage_conflicted`; any critical debt attached to lineage adds `critical_epistemic_lineage_debt`.

- [ ] **Step 4: Make `close_live()` scoped**

Derive canonical scope internally. Caller never supplies authoritative scope. Issue a v2 certificate from target risk, scope digest, scoped verification digest, counted receipt IDs and relevant lineage debt IDs.

- [ ] **Step 5: Make certificate validation mode-aware**

V2 validation recomputes `close_live()` and requires exact equality. V1 validation reconstructs canonical v1 snapshot and uses `close_snapshot()` so historical certificates remain auditable/valid under v1 semantics.

- [ ] **Step 6: Run complete A1–A8 Truth suite**

Run: `python -m pytest -q tests/test_truth_knowledge_*.py`

Expected: all Truth contracts pass.

- [ ] **Step 7: Commit**

Commit message: `feat: issue dependency-scoped truth certificates`

### Task 6: Harden malformed/forged scoped state

**Files:**
- Modify as needed: `nolane/external_core/epistemic_truth.py`
- Modify as needed: `nolane/external_core/verification_truth.py`
- Modify as needed: `nolane/external_core/assurance_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave8.py`

**Interfaces:**
- Consumes the scoped types created in Tasks 3–5.
- Produces fail-closed restore/validation behavior for omitted dependencies, mixed-mode serialized rows, duplicate identities and forged scope/certificate state.

- [ ] **Step 1: Add adversarial serialization tests**

Mutate canonical states by deleting an ancestor ID, competitor ID, evidence ID, changing a scope digest, adding duplicate set IDs, or mixing v1/v2 fields. Content tamper must fail restore when detectable; recomputed forged content must fail live canonical validation.

- [ ] **Step 2: Implement minimal validation gaps exposed by RED**

Do not add unrelated refactors. Every acceptance failure must correspond to a named invariant in the A8 spec.

- [ ] **Step 3: Run all Truth contracts**

Run: `python -m pytest -q tests/test_truth_knowledge_*.py`

Expected: all pass.

- [ ] **Step 4: Commit**

Commit message: `test: harden scoped truth state against forgery`

### Task 7: Update canonical documentation and CI authority

**Files:**
- Modify: `CURRENT/TRUTH_KNOWLEDGE.md`
- Verify: `.github/workflows/truth-knowledge-a.yml`
- Verify: `.github/workflows/refoundation-epoch0-wave1.yml`
- Test: `tests/test_truth_knowledge_repository_authority.py`

**Interfaces:**
- Documents v1 global compatibility versus v2 canonical scoped live issuance.
- Keeps workflow isolation unchanged; wildcard `tests/test_truth_knowledge_*.py` must include A8 automatically.

- [ ] **Step 1: Update CURRENT Truth law**

Document fixed-point dependency scope, scoped evidence/verification projection, ancestor contradiction/debt veto, v1/v2 compatibility, and live revalidation rules. Replace stale candidate wording with accepted A1–A7 baseline + A8 candidate wording while branch is open.

- [ ] **Step 2: Confirm subprotocol registry remains five-parent/five-helper**

No new binding row is expected. Run repository authority test to prove helpers did not seize canonical authority.

- [ ] **Step 3: Confirm CI wildcard coverage and isolation**

A-specific push gate and Refoundation PR gate already use `tests/test_truth_knowledge_*.py`; modify workflows only if verification proves A8 is not covered.

- [ ] **Step 4: Run repository audit**

Run: `python -m nolane.repository.audit --check`

Expected: fresh audit, no new migration debt.

- [ ] **Step 5: Commit**

Commit message: `docs: define A8 scoped truth authority law`

### Task 8: Final exact-head verification and integration

**Files:**
- No semantic code changes unless a gate finds a root-cause defect.

**Interfaces:**
- Produces exact-head CI evidence and merge provenance.

- [ ] **Step 1: Open/update PR against `main`**

Title: `Refoundation A8: dependency-scoped Truth binding`

PR body records RED proof, GREEN proof, exact head, scope, compatibility, and deferred work.

- [ ] **Step 2: Require focused Python 3.11 + 3.13 GREEN**

Verify compile, all `test_truth_knowledge_*.py`, and repository audit.

- [ ] **Step 3: Require Refoundation Epoch 0 Python 3.11 + 3.13 GREEN**

Verify Refoundation contracts, Truth contracts, 67/67 dossier freshness, repository audit, zero-loss evidence, organization/campaign/execution regressions, and frozen Neural metadata.

- [ ] **Step 4: Review diff/threads**

Confirm no B/C/etc ownership changes, no duplicate authority, no unresolved review thread, and no unrelated file changes.

- [ ] **Step 5: Merge with expected-head pin**

Use squash merge only after all final gates are green on the exact head.

- [ ] **Step 6: Verify `main`**

Confirm PR is merged and `main` points to the returned merge SHA.
