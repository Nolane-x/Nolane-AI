# A16 Observation Completeness / Missingness Truth v10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical observation-requirement/result layer so missing, censored, unavailable, timed-out, or interfered observations cannot be mistaken for negative evidence or complete verification.

**Architecture:** Preserve A15/v9 as an immutable audit layer. Add five v10 sidecars beneath the existing five Family-A authorities: Knowledge owns required observation slots, Evidence owns append-only observation result revisions, Epistemic wraps exact v9 scope with observation completeness/debt, Verification binds receipts to exact v10 observation state, and Assurance recomputes v10 closure live. Empty observation registries must be behaviorally equivalent to v9.

**Tech Stack:** Python 3.11/3.13, frozen dataclasses, canonical SHA-256 digests through `nolane.core.canonical_digest.canonical_digest`, pytest, GitHub Actions, existing Family-A Truth protocols.

**Spec:** `docs/superpowers/specs/2026-09-01-truth-knowledge-a16-observation-completeness-design.md`

## Global Constraints

- Family A remains exactly five canonical authorities; all A16 helpers expose only `PARENT_COMPONENT_ID` and never `COMPONENT_ID`.
- Historical v1–v9 protocol strings and serialized meanings are immutable.
- Binding mode is exactly `observation-context-dependence-defeasible-justification-provenance-lineage-temporal-v10`.
- Observation bookkeeping never creates or mutates `TruthEvidence`.
- Non-`OBSERVED` outcomes never become support/refutation and never mint verification independence.
- Relevant-only projection determines staleness; unrelated observation mutations do not stale a target.
- Empty requirement/result state reproduces v9 behavior.
- Production code is written only after a focused failing test has been observed on GitHub Actions.

---

### Task 1: Knowledge-owned observation requirements

**Files:**
- Create: `tests/test_truth_knowledge_hardening_wave16_observation_requirements.py`
- Create: `nolane/external_core/knowledge_observation_truth.py`

**Interfaces:**
- Consumes: `KnowledgeClaim`, `KnowledgeLedger`, `EvidenceChannel`, `canonical_digest`.
- Produces:
  - `ObservationRequirement.create(*, claim: KnowledgeClaim, observation_id: str, channel: EvidenceChannel) -> ObservationRequirement`
  - `ObservationRequirementSetRevision.create(*, claim: KnowledgeClaim, revision: int = 1, predecessor_digest: str = "", requirements: tuple[ObservationRequirement, ...]) -> ObservationRequirementSetRevision`
  - `ObservationRequirementRegistry.register(row, *, knowledge: KnowledgeLedger)`
  - `current(claim_id)`, `requirements(claim_id)`, `projection_state(claim_ids)`, `projection_digest(claim_ids)`, `to_state()`, `from_state(...)`.

- [ ] **Step 1: Write the failing test**

Cover exact claim/content binding, canonical requirement ordering, unique observation IDs, revision 1/+1, predecessor mismatch rejection, claim-content rebind rejection, explicit `unconstrained` projection, deterministic restore, duplicate serialized revision rejection, and unexpected-field rejection.

Representative assertion:

```python
claim = _claim("claim.target")
req = ObservationRequirement.create(
    claim=claim,
    observation_id="obs.case.001",
    channel=EvidenceChannel.TEST,
)
revision = ObservationRequirementSetRevision.create(
    claim=claim,
    requirements=(req,),
)
registry.register(revision, knowledge=knowledge)
assert registry.requirements(claim.claim_id) == (req,)
```

- [ ] **Step 2: Run the focused Truth workflow and verify RED**

Expected failure before implementation: `ModuleNotFoundError: No module named 'nolane.external_core.knowledge_observation_truth'`.

- [ ] **Step 3: Implement the minimal requirement sidecar**

Use immutable dataclasses, strict `_unexpected` restore checks, exact protocol strings `truth-observation-requirements-v10` and `truth-observation-requirements-projection-v10`, sorted canonical tuples, and append-only revision history.

- [ ] **Step 4: Run focused tests and confirm GREEN on Python 3.11 and 3.13**

- [ ] **Step 5: Commit**

Commit message: `feat: add A16 observation requirements`.

---

### Task 2: Evidence-owned observation results

**Files:**
- Create: `tests/test_truth_knowledge_hardening_wave16_observation_results.py`
- Create: `nolane/external_core/evidence_observation_truth.py`

**Interfaces:**
- Consumes: `ObservationRequirement`, `EvidenceLedger`, `TruthEvidence`, `EvidenceChannel`.
- Produces:
  - `ObservationOutcome` enum with `observed`, `missing`, `censored`, `unavailable`, `timeout`, `interfered`.
  - `ObservationResultRevision.create(*, requirement: ObservationRequirement, revision: int = 1, predecessor_digest: str = "", outcome: ObservationOutcome, evidence: TruthEvidence | None = None, reason: str = "")`.
  - `ObservationResultLedger.register(row, *, evidence: EvidenceLedger)`.
  - `current(requirement_digest)`, `history(requirement_digest)`, `projection_state(requirements)`, `projection_digest(requirements)`, `to_state()`, `from_state(...)`.

- [ ] **Step 1: Write failing result tests**

Required cases:

```python
with pytest.raises(ValueError, match="observed result requires evidence"):
    ObservationResultRevision.create(
        requirement=req,
        outcome=ObservationOutcome.OBSERVED,
    )

with pytest.raises(ValueError, match="non-observed result cannot bind evidence"):
    ObservationResultRevision.create(
        requirement=req,
        outcome=ObservationOutcome.TIMEOUT,
        evidence=evidence_row,
        reason="deadline",
    )
```

Also test wrong subject/channel, revision/predecessor mismatch, requirement rebind, evidence digest tamper, exact restore, duplicate serialization, and unrelated projection stability.

- [ ] **Step 2: Observe RED for missing evidence sidecar**

- [ ] **Step 3: Implement minimal result ledger**

`OBSERVED` must bind exact Evidence ID/content digest and validate subject/channel. Every non-observed result requires a non-empty reason and has empty Evidence binding. Projection must distinguish `unrecorded` from each explicit outcome.

- [ ] **Step 4: Verify GREEN**

- [ ] **Step 5: Commit**

Commit message: `feat: add A16 observation result ledger`.

---

### Task 3: Epistemic v10 observation completeness

**Files:**
- Create: `tests/test_truth_knowledge_hardening_wave16_scope.py`
- Create: `nolane/external_core/epistemic_observation_truth.py`

**Interfaces:**
- Consumes exact `ContextTruthScope`/`ContextEpistemicJudge`, `ObservationRequirementRegistry`, `ObservationResultLedger`, and all v9 judge dependencies.
- Produces:
  - `OBSERVATION_BINDING_MODE` exact v10 string.
  - `ObservationTruthScope` with `audit_context_scope`, observation requirement/result digests, required requirement digests/IDs, incomplete partitions, merged v10 assessments/debts, digest.
  - `ObservationEpistemicJudge.relation_aware_temporal_scope(...) -> ObservationTruthScope`.
  - `ObservationEpistemicJudge.validate_scope(...) -> bool`.

- [ ] **Step 1: Write failing scope tests**

Tests must prove:

```python
scope = judge.relation_aware_temporal_scope(...)
assert scope.audit_context_scope.assessment(target).disposition is EpistemicDisposition.SUPPORTED
assert scope.assessment(target).disposition is EpistemicDisposition.UNKNOWN
assert any(d.reason == "required_observation_unrecorded" for d in scope.debts)
```

Then add one test for each explicit incomplete outcome, an observed exact-Evidence case that remains supported, unrelated requirement/result mutation stability, relevant revision staleness, dead/unreachable branch non-veto, serialization hardening, and empty-state v9 equivalence.

- [ ] **Step 2: Observe RED for missing v10 epistemic module**

- [ ] **Step 3: Implement v10 as a wrapper over canonical v9**

Algorithm:

1. Recompute exact v9 `ContextTruthScope`.
2. Collect requirements only for `scope_claim_ids` that are target-reachable through the v9 scope.
3. Project requirement and result state only for those requirements.
4. Emit one canonical `EpistemicDebt` per incomplete relevant requirement.
5. For a v9-supported claim with an incomplete own/live-lineage requirement, replace its v10 assessment with `UNKNOWN`; never convert missingness to REFUTED.
6. Preserve v9 assessments otherwise.
7. Bind every derived field in the v10 digest.

- [ ] **Step 4: Verify GREEN and v9 compatibility**

- [ ] **Step 5: Commit**

Commit message: `feat: add A16 observation completeness scope`.

---

### Task 4: Verification v10 binding

**Files:**
- Create: `tests/test_truth_knowledge_hardening_wave16_verification.py`
- Create: `nolane/external_core/verification_observation_truth.py`

**Interfaces:**
- Consumes `ObservationTruthScope`, v9 source/context/provenance/dependence mechanisms, `ObservationRequirementRegistry`, `ObservationResultLedger`.
- Produces:
  - `ObservationTruthVerificationReceipt`.
  - `ObservationTruthVerificationCoverage`.
  - `ObservationTruthVerificationLedger`.

- [ ] **Step 1: Write failing verification tests**

Prove exact scope binding, truth/temporal context binding, requirement/result projection staleness, negative receipt retention, A14 common-basis collapse, no independence from observation IDs/outcomes, and rejection of v9 receipts.

Representative validity rule:

```python
assert not ledger.receipt_is_current(
    receipt,
    scope=changed_observation_scope,
    truth_context=truth_context,
    temporal_context=temporal_context,
)
```

- [ ] **Step 2: Observe RED**

Expected missing module/API failure.

- [ ] **Step 3: Implement dedicated v10 ledger**

Reuse the v9 independence algorithm exactly; add exact v10 protocol/binding checks and live requirement/result projection validation. Do not use context or observation identity in independence keys.

- [ ] **Step 4: Verify GREEN**

- [ ] **Step 5: Commit**

Commit message: `feat: bind A16 verification to observation completeness`.

---

### Task 5: Assurance v10 closure

**Files:**
- Create: `tests/test_truth_knowledge_hardening_wave16_assurance.py`
- Create: `nolane/external_core/assurance_observation_truth.py`

**Interfaces:**
- Consumes `ObservationEpistemicJudge`, `ObservationTruthVerificationLedger`, all exact v9 dependencies, requirement/result registries.
- Produces:
  - `ObservationTruthClosureCertificate`.
  - `ObservationTruthAssuranceGate.evaluate(...)`.
  - `ObservationTruthAssuranceGate.validate_certificate(...)`.

- [ ] **Step 1: Write failing assurance tests**

Cover:

- high-risk closure with complete observed requirements and two independent channels/sources;
- identical verifier basis collapse remains closed=false;
- any live target-reachable incomplete observation blocks closure;
- relevant result revision stales certificate;
- unrelated result revision preserves certificate;
- v9 certificate rejected by v10 gate.

- [ ] **Step 2: Observe RED**

- [ ] **Step 3: Implement v10 closure as live recomputation**

Reuse accepted v9 thresholds. Add `observation_completeness_invalid`/`critical_observation_debt` reasons where appropriate. Never allow a certificate to self-authenticate; `validate_certificate` must rebuild canonical v10 state and compare exact content.

- [ ] **Step 4: Verify GREEN**

- [ ] **Step 5: Commit**

Commit message: `feat: gate A16 assurance on observation completeness`.

---

### Task 6: Authority, compatibility, restore and anti-laundering hardening

**Files:**
- Create: `tests/test_truth_knowledge_hardening_wave16_authority.py`
- Create: `tests/test_truth_knowledge_hardening_wave16_compatibility.py`
- Create: `tests/test_truth_knowledge_hardening_wave16_protocol_restore.py`

**Interfaces:** Existing five v10 sidecars.

- [ ] **Step 1: Add authority test**

Assert exact parent IDs:

```python
assert knowledge_observation_truth.PARENT_COMPONENT_ID == "external.knowledge"
assert evidence_observation_truth.PARENT_COMPONENT_ID == "external.evidence"
assert epistemic_observation_truth.PARENT_COMPONENT_ID == "external.epistemic"
assert verification_observation_truth.PARENT_COMPONENT_ID == "external.verification"
assert assurance_observation_truth.PARENT_COMPONENT_ID == "external.assurance"
for module in modules:
    assert not hasattr(module, "COMPONENT_ID")
```

- [ ] **Step 2: Add compatibility test**

Build identical state with empty observation registries and assert v10 audit scope equals v9, target disposition equals v9, verification independent-source/channel counts equal v9, and closure equals v9.

- [ ] **Step 3: Add tamper/restore tests**

Reject protocol downgrade, unexpected fields, duplicate requirement/result revisions, changed requirement digest, changed Evidence content digest, changed scope projection digest, and v9 receipt/certificate masquerade.

- [ ] **Step 4: Run full `tests/test_truth_knowledge_*.py`**

Expected: all green on Python 3.11 and 3.13.

- [ ] **Step 5: Commit**

Commit message: `test: harden A16 observation truth protocols`.

---

### Task 7: Canonical CI and candidate documentation

**Files:**
- Modify: `.github/workflows/truth-knowledge-a.yml`
- Create: `CURRENT/TRUTH_KNOWLEDGE_A16_CANDIDATE.md`

- [ ] **Step 1: Extend workflow path filters**

Add all five A16 sidecars.

- [ ] **Step 2: Extend compile gate**

Rename compile step through A16/v10 and compile all five new modules.

- [ ] **Step 3: Write candidate record**

Record exact branch/head, architecture, RED commits/runs, GREEN exact-head Truth run, compatibility/authority invariants, and explicit `NOT ACCEPTED` status until production integration.

- [ ] **Step 4: Run fresh exact-head Truth A CI**

Require both Python 3.11 and 3.13 plus repository audit GREEN on the same immutable head.

- [ ] **Step 5: Commit**

Commit message: `ci: gate Truth Knowledge A16 observation completeness`.

---

### Task 8: Integration, Refoundation and production acceptance

**Files:**
- No production file outside intended Family-A A16 surface.
- Later acceptance-only changes: `CURRENT/TRUTH_KNOWLEDGE.md`, `docs/superpowers/acceptance/TRUTH_KNOWLEDGE_A16_ACCEPTANCE.md`, and removal of candidate file.

- [ ] **Step 1: Fetch latest `main` and race-check**

If main advanced, rebuild an integration branch from the new main and overlay only the exact A16 intended files; never overwrite concurrent specialist B/C/D/E work.

- [ ] **Step 2: Verify intended-only diff**

No unrelated production files may change.

- [ ] **Step 3: Run fresh Truth A on integrated exact head**

- [ ] **Step 4: Run full Refoundation Epoch 0 on exact synthetic merge state**

- [ ] **Step 5: Check PR review surface and mergeability**

Require no unresolved reviews/threads/comments and exact tested head.

- [ ] **Step 6: Expected-head production merge**

Merge only if latest-main race guard still matches.

- [ ] **Step 7: Create separate acceptance seal**

Promote CURRENT authority to A1–A16, preserve historical acceptance records, record exact production evidence, remove stale candidate file.

- [ ] **Step 8: Run seal Truth + Refoundation proof and expected-head merge**

- [ ] **Step 9: Post-merge verify canonical main**

Confirm exact parents/tree, A1–A16 CURRENT status, acceptance artifact, and absence of candidate file.
