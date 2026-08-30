# A10 Relation Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add canonical relation cardinality authority and a relation-aware Truth scope v3 that eliminates false contradictions for multi-valued relations while failing closed on exclusive conflicts and unspecified cardinality.

**Architecture:** `external.knowledge` gains an append-only content-addressed `RelationSemanticsRegistry`. A new v3 Truth scope consumes a scoped registry projection and computes relation-aware fixed-point competitor closure. Verification and Assurance gain an exact v3 binding mode while preserving v1 and A8-v2 serialized identities and mode selection.

**Tech Stack:** Python 3.11/3.13, frozen dataclasses, enums, canonical SHA-256 identity via `nolane.core.canonical_digest.canonical_digest`, pytest, GitHub Actions Refoundation gates.

**Spec:** `docs/superpowers/specs/2026-08-30-truth-knowledge-a10-relation-semantics-design.md`

## Global Constraints

- Family A remains exactly the existing canonical authorities; no sixth runtime component.
- `external.knowledge` remains owned by `nolane.memory.knowledge`.
- A1–A8 v1/v2 serialized payloads and digests remain exact historical semantics.
- Relation policy is parent-owned and cannot be claim-declared.
- Relation revisions are append-only, monotonic and predecessor-bound.
- V3 live validation recomputes Knowledge + Evidence + Relation Semantics authority.
- A10 does not implement temporal validity, ontology inference, source trust, inverse/transitive relations, or verification-polarity coherence.
- Acceptance requires focused Truth and full Refoundation gates on Python 3.11 and 3.13.

---

### Task 1: Canonical relation-semantics authority

**Files:**
- Modify: `nolane/memory/knowledge.py`
- Test: `tests/test_truth_knowledge_hardening_wave10_relation_registry.py`

**Interfaces:**
- Produces: `RelationCardinality`, `RelationSemanticsRevision.create(...)`, `RelationSemanticsRegistry.record(...)`, `current(...)`, `cardinality(...)`, `projection_state(...)`, `projection_digest(...)`, `to_state()`, `from_state(...)`.
- Consumes: `nolane.core.canonical_digest.canonical_digest`.

- [ ] **Step 1: Write RED registry contracts**

Create tests proving:

```python
registry = RelationSemanticsRegistry()
r1 = RelationSemanticsRevision.create(
    relation="status", revision=1,
    cardinality=RelationCardinality.EXCLUSIVE,
    previous_digest="",
)
registry.record(r1)
assert registry.cardinality("status") is RelationCardinality.EXCLUSIVE
assert registry.cardinality("speaks") is RelationCardinality.UNSPECIFIED
```

Also prove same-revision semantic collision, revision skip, rollback, wrong predecessor and fork fail closed; `from_state()` rejects duplicate rows/tamper; relation projection digest ignores unrelated policies but changes for a relevant revision.

- [ ] **Step 2: Run the focused RED file**

Run:
`python -m pytest -q tests/test_truth_knowledge_hardening_wave10_relation_registry.py`

Expected: import/API failures because relation semantics authority does not yet exist.

- [ ] **Step 3: Implement the minimal canonical registry**

Add to `nolane.memory.knowledge`:

```python
class RelationCardinality(str, Enum):
    EXCLUSIVE = "exclusive"
    MULTI_VALUED = "multi_valued"
    UNSPECIFIED = "unspecified"

@dataclass(frozen=True, slots=True)
class RelationSemanticsRevision:
    relation: str
    revision: int
    cardinality: RelationCardinality
    previous_digest: str
    digest: str
```

`record()` accepts revision 1 only without predecessor, then exact `n+1` with exact previous digest. Same revision is idempotent only for the identical row. Store all revisions. `projection_state(relations)` emits canonical sorted rows; unregistered relations emit `{"relation": name, "status": "unspecified"}`. `projection_digest()` hashes only that projection.

Advance only `external.knowledge` software component revision if repository version contracts require it for this accepted parent API change.

- [ ] **Step 4: Run registry tests + existing Truth tests**

Run:
`python -m pytest -q tests/test_truth_knowledge_hardening_wave10_relation_registry.py tests/test_truth_knowledge_*.py`

Expected: PASS with no A1–A8 failures.

- [ ] **Step 5: Commit registry GREEN**

Commit message:
`feat: add canonical relation semantics registry`

---

### Task 2: Relation-aware Knowledge scope and Epistemic v3

**Files:**
- Modify: `nolane/external_core/knowledge_truth.py`
- Modify: `nolane/external_core/epistemic_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave10_relation_scope.py`

**Interfaces:**
- Consumes: `RelationSemanticsRegistry`, `RelationCardinality` from `nolane.memory.knowledge`.
- Produces: `KnowledgeLedger.truth_scope_claim_ids_v3(claim_id, relation_semantics)`, `TruthRelationAwareScope`, `EpistemicJudge.relation_aware_dependency_scope(...)`, `validate_relation_aware_scope(...)`.

- [ ] **Step 1: Write RED scope contracts**

Build supported claims:

```text
alice --speaks--> English
alice --speaks--> French
server --status--> online
server --status--> offline
```

Prove MULTI_VALUED `speaks` does not add the other object to a target scope or contradiction; EXCLUSIVE `status` does; UNSPECIFIED includes the other object but produces `relation_semantics_unspecified_for_multiple_values` debt instead of fabricated contradiction. Add ancestor propagation and fixed-point competitor ancestry tests.

- [ ] **Step 2: Run RED scope tests**

Run:
`python -m pytest -q tests/test_truth_knowledge_hardening_wave10_relation_scope.py`

Expected: missing v3 scope APIs and current v2 false-conflict behavior exposed by the tests.

- [ ] **Step 3: Implement relation-aware fixed point**

Add `truth_scope_claim_ids_v3()` without modifying A8 `truth_scope_claim_ids()`:

```python
if cardinality is RelationCardinality.MULTI_VALUED:
    competitors = ()
else:
    competitors = claims with same subject/relation and different object
```

For every competitor, include transitive ancestry and repeat to fixed point.

Add `TruthRelationAwareScope` with protocol `truth-dependency-scope-v3`, binding relevant relation IDs and `relation_semantics_digest` in addition to A8 scoped state.

- [ ] **Step 4: Implement relation-aware conflict/debt projection**

Do not reuse global/v2 contradiction rows for cardinality decisions. Per supported `(subject, relation)` group:

- EXCLUSIVE + >1 distinct object: contradiction + `competing_supported_propositions` debt;
- MULTI_VALUED: no cardinality conflict/debt;
- UNSPECIFIED + >1 distinct object: `relation_semantics_unspecified_for_multiple_values` debts, no contradiction.

Retain evidence-lineage and UNKNOWN/CONTRADICTED debts for scoped claims.

- [ ] **Step 5: Run scope + full Truth tests**

Run:
`python -m pytest -q tests/test_truth_knowledge_hardening_wave10_relation_scope.py tests/test_truth_knowledge_*.py`

Expected: PASS and unchanged v1/v2 contracts.

- [ ] **Step 6: Commit scope GREEN**

Commit message:
`feat: add relation-aware truth scope v3`

---

### Task 3: Verification v3 exact-mode binding

**Files:**
- Modify: `nolane/external_core/verification_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave10_relation_verification.py`

**Interfaces:**
- Produces: `RELATION_SCOPED_BINDING_MODE = "relation-aware-scope-v3"`, v3 receipt construction/restore, `relation_scoped_receipts()`, `coverage_relation_scoped()`, `relation_scoped_digest()`.
- Preserves: v1 and `dependency-scope-v2` payloads byte-semantically.

- [ ] **Step 1: Write RED mode-separation contracts**

Prove a v3 receipt serializes `binding_mode=relation-aware-scope-v3`, contains no global fields, and round-trips. Prove v2 lookup never returns v3 receipts and v3 lookup never returns v2 receipts even when claim/scope strings are equal. Prove mixed global+v3 state fails closed.

- [ ] **Step 2: Run RED verification tests**

Run:
`python -m pytest -q tests/test_truth_knowledge_hardening_wave10_relation_verification.py`

Expected: unsupported binding mode / missing APIs.

- [ ] **Step 3: Implement exact mode branching**

Keep old constructor behavior: `scope_digest` without explicit mode still means A8 v2. V3 requires explicit `binding_mode=RELATION_SCOPED_BINDING_MODE`. Serialize each mode with its exact constant. Keep `scoped_receipts()` v2-only and add a distinct v3 selector/projection.

- [ ] **Step 4: Run verification + serialization regression**

Run:
`python -m pytest -q tests/test_truth_knowledge_hardening_wave10_relation_verification.py tests/test_truth_knowledge_hardening_wave8_serialization.py tests/test_truth_knowledge_*.py`

Expected: PASS.

- [ ] **Step 5: Commit Verification GREEN**

Commit message:
`feat: bind verification to relation-aware scope v3`

---

### Task 4: Assurance v3 and fail-closed live mode selection

**Files:**
- Modify: `nolane/external_core/assurance_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave10_relation_assurance.py`

**Interfaces:**
- Consumes: `TruthRelationAwareScope`, `RelationSemanticsRegistry`, v3 Verification APIs.
- Produces: v3 certificate construction/restore, `_close_relation_aware(...)`, optional `relation_semantics` parameter on `close_live()` and `validate_certificate()`.

- [ ] **Step 1: Write RED Assurance contracts**

Prove:

- a MULTI_VALUED target with valid v3 verification can close despite another supported object;
- EXCLUSIVE competitor blocks closure;
- UNSPECIFIED multiple supported values blocks closure with explicit relation-semantics ambiguity reason;
- the same ambiguity/conflict on an ancestor blocks descendant closure;
- relevant relation policy revision invalidates the old v3 certificate;
- unrelated policy revision leaves the certificate valid;
- once target has v3 history, stale v3 receipts do not fall back to v2;
- a v3 certificate cannot validate without live canonical relation semantics.

- [ ] **Step 2: Run RED Assurance tests**

Run:
`python -m pytest -q tests/test_truth_knowledge_hardening_wave10_relation_assurance.py`

Expected: v3 issuance/validation APIs missing.

- [ ] **Step 3: Implement v3 certificate mode**

Extend `TruthClosureCertificate` additively so scoped serialization branches by exact binding mode. V1 and v2 payloads remain unchanged. V3 uses the existing scoped certificate fields but serializes `binding_mode=relation-aware-scope-v3`.

- [ ] **Step 4: Implement live v3 closure**

`close_live(..., relation_semantics=None)` preserves exact A8 behavior when registry is absent. When registry is present:

1. if target has any v3 verification history, recompute canonical v3 scope and remain v3 even when current v3 receipts are stale;
2. otherwise preserve historical v2/v1 mode selection.

V3 blocks target/ancestor exclusive contradiction, target/ancestor `relation_semantics_unspecified_for_multiple_values` debt, existing critical debt, negative verification, insufficient source independence or channel diversity.

- [ ] **Step 5: Implement mode-exact certificate validation**

For v3 certificate, require `relation_semantics` and recompute v3 closure; never dispatch v3 through v2. Exact certificate equality remains required.

- [ ] **Step 6: Run Assurance + full Truth tests**

Run:
`python -m pytest -q tests/test_truth_knowledge_hardening_wave10_relation_assurance.py tests/test_truth_knowledge_*.py`

Expected: PASS.

- [ ] **Step 7: Commit Assurance GREEN**

Commit message:
`feat: add relation-aware assurance v3`

---

### Task 5: Canonical documentation, authority audit and full acceptance

**Files:**
- Modify: `CURRENT/TRUTH_KNOWLEDGE.md`
- Test: `tests/test_truth_knowledge_hardening_wave10_authority.py`
- Existing CI: `.github/workflows/truth-knowledge-a.yml`
- Existing CI: `.github/workflows/refoundation-epoch0.yml`

**Interfaces:**
- Produces: accepted A10 source-of-truth only after exact final-head gates are green.

- [ ] **Step 1: Add authority/compatibility RED contracts**

Prove exactly five family-A canonical parent authorities remain; relation semantics classes live in `nolane.memory.knowledge`; Truth helpers still have no `COMPONENT_ID`; v1/v2 fixture serialization remains unchanged; Knowledge component revision is consistent with repository version law.

- [ ] **Step 2: Run focused Truth suite**

Run:
`python -m py_compile nolane/memory/knowledge.py nolane/external_core/knowledge_truth.py nolane/external_core/epistemic_truth.py nolane/external_core/verification_truth.py nolane/external_core/assurance_truth.py`

Then:
`python -m pytest -q tests/test_truth_knowledge_*.py`

Then:
`python -m nolane.repository.audit --check`

Expected: all PASS on Python 3.11 and 3.13 in the Truth Knowledge workflow.

- [ ] **Step 3: Update canonical A documentation**

Document A10 as candidate first: parent-owned relation authority, revision lineage, v3 scope/conflict law, v1/v2 compatibility and exact acceptance gates. Change to accepted only on the exact final candidate after all final gates pass.

- [ ] **Step 4: Integrate latest main without overwriting concurrent work**

Before PR/final proof, compare current `main` and the A10 branch. If A9 temporal-validity or another workstream has merged, integrate current `main` as an ancestor while preserving its tree outside A10 paths. Re-run all gates on the integrated exact head.

- [ ] **Step 5: Run full Refoundation acceptance**

Require exact-head success on Python 3.11 and 3.13 for Refoundation contracts, Truth contracts, 67/67 dossier freshness, repository audit, zero-loss evidence, organization/campaign/execution regressions and frozen Neural metadata.

- [ ] **Step 6: Review PR scope and merge with head pin**

Require no unresolved review threads, A-only changed paths, `behind=0`, and `mergeable=true`. Merge only with `expected_head_sha=<exact green head>`.

- [ ] **Step 7: Verify post-merge main**

Confirm `main` points to the returned merge commit, merged tree equals the tested candidate tree, PR is `merged=true`, and `CURRENT/TRUTH_KNOWLEDGE.md` on `main` records the accepted A10 baseline.
