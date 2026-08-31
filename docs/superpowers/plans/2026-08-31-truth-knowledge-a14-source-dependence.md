# A14 Source Dependence v8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add canonical common-basis dependence to Family-A verification so distinct controllers cannot mint false independence when they share an epistemic basis.

**Architecture:** Keep A1–A13 immutable. Add four additive v8 sidecars under Evidence, Epistemic, Verification and Assurance. V8 wraps the exact live A13 scope, binds a relevant-only source-dependence projection, and collapses passing verifiers into conservative transitive dependence components.

**Tech Stack:** Python dataclasses, canonical digests, pytest, GitHub Actions Python 3.11/3.13.

**Spec:** `docs/superpowers/specs/2026-08-31-truth-knowledge-a14-source-dependence-design.md`

## Global Constraints

- Exactly five canonical Family-A authorities; every A14 module uses `PARENT_COMPONENT_ID`, never `COMPONENT_ID`.
- A14 binding mode is `dependence-defeasible-justification-provenance-lineage-temporal-v8`.
- A1–A13 classes and protocols remain unchanged.
- Missing dependence metadata cannot mint v8 independence.
- Relevant-only dependence projection: unrelated revisions cannot stale a target.
- TDD RED→GREEN before acceptance claims.

---

### Task 1: Evidence source-dependence registry

**Files:**
- Create: `nolane/external_core/evidence_dependence_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave14_dependence_registry.py`

**Interfaces:**
- Produces: `SourceDependenceRevision`, `SourceDependenceRegistry`, `TRUTH_PROTOCOL`, `PROJECTION_PROTOCOL`, `PARENT_COMPONENT_ID`.

- [ ] Write RED tests for strict revision 1/+1 predecessor binding, canonical non-empty basis IDs, relevant-only projection, missing state, restore duplicate/protocol/sequence/predecessor attacks.
- [ ] Run focused test and verify failure because the v8 module does not exist.
- [ ] Implement the minimal append-only registry using `canonical_digest`.
- [ ] Run the focused tests to GREEN and commit.

### Task 2: Dependence-bound epistemic scope

**Files:**
- Create: `nolane/external_core/epistemic_dependence_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave14_scope.py`

**Interfaces:**
- Consumes: `DefeasibleEpistemicJudge`, `DefeasibleTruthScope`, `SourceDependenceRegistry`.
- Produces: `DEPENDENCE_BINDING_MODE`, `DependenceTruthScope`, `DependenceEpistemicJudge`.

- [ ] Write RED tests proving v8 wraps exact v7 state, relevant decision/source dependence revision stales v8 scope, unrelated dependence revision does not, and serialized scope cannot self-authenticate.
- [ ] Run focused test RED.
- [ ] Implement v8 wrapper scope with nested v7 state plus relevant dependence projection digest.
- [ ] Implement live `validate_scope()` recomputation.
- [ ] Run focused tests GREEN and commit.

### Task 3: Dependence-aware verification

**Files:**
- Create: `nolane/external_core/verification_dependence_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave14_verification.py`

**Interfaces:**
- Consumes: `DependenceTruthScope`, `SourceDependenceRegistry`, `SourceProvenanceRegistry`, accepted Evidence temporal/provenance APIs.
- Produces: `DependenceTruthVerificationReceipt`, `DependenceTruthVerificationCoverage`, `DependenceTruthVerificationLedger`.

- [ ] Write RED tests for same-basis collapse, transitive overlap collapse, decision-basis exclusion, disjoint basis independence, missing metadata fail-closed, stale verifier-dependence invalidation, negative receipt retention, v7 receipt masquerade rejection.
- [ ] Run focused RED.
- [ ] Implement dedicated v8 receipt and exact scope binding.
- [ ] Implement provenance + dependence validation.
- [ ] Implement deterministic union-find/group collapse over shared controller keys and shared basis IDs.
- [ ] Ensure any component touching a decision controller or decision basis contributes zero independence credit.
- [ ] Run focused tests GREEN and commit.

### Task 4: Dependence-aware assurance

**Files:**
- Create: `nolane/external_core/assurance_dependence_truth.py`
- Test: `tests/test_truth_knowledge_hardening_wave14_assurance.py`

**Interfaces:**
- Consumes: `DependenceEpistemicJudge`, `DependenceTruthVerificationLedger`, A13 semantic fields through nested v7 scope.
- Produces: `DependenceTruthClosureCertificate`, `DependenceTruthAssuranceGate`.

- [ ] Write RED tests proving HIGH closure fails when two controller-distinct verifiers share a basis, succeeds for two disjoint bases/channels, fails on incomplete dependence metadata, and certificate stales on relevant but not unrelated dependence revision.
- [ ] Run focused RED.
- [ ] Implement v8 closure preserving all A13 vetoes and thresholds.
- [ ] Bind certificate to v8 scope and v8 verification projection; implement live validation.
- [ ] Run focused tests GREEN and commit.

### Task 5: Authority, compatibility and CI surface

**Files:**
- Create: `tests/test_truth_knowledge_hardening_wave14_authority.py`
- Create: `tests/test_truth_knowledge_hardening_wave14_compatibility.py`
- Modify: `.github/workflows/truth-knowledge-a.yml`
- Modify: `CURRENT/TRUTH_KNOWLEDGE.md`

**Interfaces:**
- Locks protocol separation and canonical ownership.

- [ ] Test all four sidecars expose the expected `PARENT_COMPONENT_ID` and no `COMPONENT_ID`.
- [ ] Test v7 objects remain valid historical objects and cannot masquerade as v8.
- [ ] Add all four v8 modules to Truth workflow path/compile surfaces.
- [ ] Record A14 as candidate only, preserving A1–A13 accepted status until production acceptance.
- [ ] Run `python -m pytest -q tests/test_truth_knowledge_*.py` and repository audit on Python 3.11/3.13.

### Task 6: Freeze, integration and production acceptance

**Files:**
- No semantic changes after freeze unless a gate exposes a defect.

- [ ] Freeze exact candidate SHA after focused Truth A GREEN.
- [ ] Verify intended diff contains only A14 Family-A modules/tests/docs/workflow/canonical candidate status.
- [ ] Re-read current `main`; integrate concurrent non-A drift without dropping either side.
- [ ] Open production PR with exact candidate/base evidence.
- [ ] Run synthetic full Refoundation on Python 3.11/3.13: Refoundation, Truth A, downstream, dossiers, audit, zero-loss evidence, Neural R2.3.
- [ ] Verify mergeable=true, exact changed files, 0 reviews/threads unless substantive review exists.
- [ ] Merge with `expected_head_sha`; verify exact merge parents and final `main`.
- [ ] Create a separate docs-only acceptance seal changing only `CURRENT/TRUTH_KNOWLEDGE.md` to A1–A14 accepted.
- [ ] Run seal Truth A + full Refoundation on exact synthetic seal tree.
- [ ] Merge seal with expected-head protection; verify final canonical file and post-merge integrity evidence.
