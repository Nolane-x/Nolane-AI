# A11 Provenance-Bound Source Independence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make A-layer verification diversity depend on canonical source-provenance lineage rather than caller-declared `source_family` labels.

**Architecture:** Add v5 sidecars beneath the existing Evidence, Epistemic, Verification and Assurance authorities. V5 wraps the accepted A9 temporal relation-aware scope, binds a relevant-only append-only provenance projection, derives independence from controller ancestry, and preserves v1–v4 byte/API compatibility.

**Tech Stack:** Python 3.11/3.13, dataclasses, canonical content digests, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-31-truth-knowledge-a11-provenance-independence-design.md`

## Global Constraints

- Preserve exactly five canonical family-A authorities.
- No A11 helper may declare `COMPONENT_ID`.
- V5 binding mode is `provenance-lineage-temporal-v5`.
- V1–v4 record/receipt/certificate shapes remain unchanged.
- Canonical identity uses `nolane.core.canonical_digest.canonical_digest` only.
- No implicit wall clock is introduced.
- All set-semantic identifiers are canonical sorted and duplicate-rejecting.
- Production changes follow RED → GREEN TDD.

---

### Task 1: Lock A11 adversarial contracts

**Files:**
- Create: `tests/test_truth_knowledge_hardening_wave11_provenance.py`
- Modify: `.github/workflows/truth-knowledge-a.yml`

**Interfaces:**
- Consumes: accepted A1–A10 APIs.
- Produces: executable A11 contract for provenance registry, v5 scope, v5 verification and v5 assurance.

- [ ] Write tests proving alias collapse, mirror/aggregate behavior, revision/cycle/restore rejection, relevant-only projection, v5 legacy-field rejection, CRITICAL Sybil failure, genuine diversity success, relevant stale invalidation and unrelated stability.
- [ ] Add future A11 modules to the focused workflow path/compile surface.
- [ ] Push the test-only checkpoint and require the focused Truth gate to be RED because A11 production modules are absent.
- [ ] Preserve the exact RED workflow run as evidence.

### Task 2: Implement canonical source-provenance lineage

**Files:**
- Create: `nolane/external_core/evidence_provenance_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave11_provenance.py`

**Interfaces:**
- Produces: `SourceProvenanceRevision.create(...)`, `SourceProvenanceRegistry.register(...)`, `current(...)`, `root_controllers(...)`, `independence_key(...)`, `projection_state(...)`, `projection_digest(...)`, `to_state()`, `from_state(...)`.

- [ ] Implement immutable predecessor-bound revisions.
- [ ] Validate parent existence and current-graph acyclicity before mutation.
- [ ] Implement controller-root closure and conservative independence key.
- [ ] Implement ancestry-complete relevant projection with explicit missing requested sources.
- [ ] Implement tamper-resistant deterministic restore.
- [ ] Run the provenance-focused tests and keep all existing A tests GREEN.

### Task 3: Bind provenance into exact epistemic scope

**Files:**
- Create: `nolane/external_core/epistemic_provenance_truth.py`

**Interfaces:**
- Consumes: `TemporalEpistemicJudge.relation_aware_dependency_scope(...)` and `SourceProvenanceRegistry.projection_digest(...)`.
- Produces: `ProvenanceTruthScope` and `ProvenanceEpistemicJudge.relation_aware_temporal_scope(...)` / `validate_scope(...)`.

- [ ] Re-derive v4 scope rather than copying temporal/relation logic.
- [ ] Derive exact source IDs from scoped Evidence.
- [ ] Bind relevant provenance projection, context and v4 scope digest into v5 digest.
- [ ] Add strict serialization field validation and live recomputation validation.

### Task 4: Replace label-counting with lineage-derived verification diversity

**Files:**
- Create: `nolane/external_core/verification_provenance_truth.py`

**Interfaces:**
- Consumes: `ProvenanceTruthScope`, `TemporalEvidenceView`, `SourceProvenanceRegistry`.
- Produces: `ProvenanceTruthVerificationReceipt`, `ProvenanceTruthVerificationCoverage`, `ProvenanceTruthVerificationLedger`.

- [ ] Define dedicated v5 receipt without `source_family`.
- [ ] Exact-bind scope/context/evidence and verifier provenance projection.
- [ ] Validate temporal evidence provenance against live Evidence state.
- [ ] Deduplicate passing independence by `independence_key(verifier_id)`.
- [ ] Retain valid multi-controller receipts for audit while giving them zero independence credit.
- [ ] Reject missing/stale provenance and legacy mixed-state restore.

### Task 5: Add provenance-aware Assurance v5

**Files:**
- Create: `nolane/external_core/assurance_provenance_truth.py`

**Interfaces:**
- Consumes: live A9 scope semantics, v5 provenance scope, v5 verification coverage.
- Produces: `ProvenanceTruthClosureCertificate`, `ProvenanceTruthAssuranceGate.close(...)`, `validate_certificate(...)`.

- [ ] Preserve A9 epistemic/relation/temporal vetoes.
- [ ] Block incomplete scoped Evidence provenance.
- [ ] Apply unchanged risk thresholds to provenance-derived controller independence and channel diversity.
- [ ] Bind exact verification projection and all live provenance-sensitive state into certificate identity.
- [ ] Recompute complete closure during validation.

### Task 6: Seal compatibility and acceptance evidence

**Files:**
- Modify: `CURRENT/TRUTH_KNOWLEDGE.md`
- Modify: `.github/workflows/truth-knowledge-a.yml`

**Interfaces:**
- Produces: documented candidate/accepted A11 boundary and CI coverage.

- [ ] Run every `tests/test_truth_knowledge_*.py` contract on Python 3.11 and 3.13.
- [ ] Run repository authority audit.
- [ ] Open an A11 PR and require full Refoundation Epoch 0 on Python 3.11/3.13.
- [ ] Verify intended-only diff and clean review surface.
- [ ] Merge with expected-head protection only after exact PR merge state is GREEN.
- [ ] Confirm post-merge `main` contains the exact verified A11 semantics.