# A13 Defeasible Truth Maintenance / Justification Undercutters v7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add canonical, provenance/temporal-bound justification undercutters so Nolane Truth can invalidate an inference path without falsifying or revoking historically valid evidence.

**Architecture:** A13 adds one Knowledge-owned append-only undercutter registry, then derives a dedicated v7 Epistemic scope, v7 Verification ledger, and v7 Assurance certificate. It preserves A1–A12 byte/domain compatibility, the exact five-authority model, A10 relation semantics, A9 temporal context, A11 controller-root independence, and A12 OR-of-AND justification semantics.

**Tech Stack:** Python dataclasses/enums, canonical digest protocol, pytest, GitHub Actions Python 3.11/3.13.

**Spec:** `docs/superpowers/specs/2026-08-31-truth-knowledge-a13-defeasible-truth-design.md`

## Global Constraints

- Keep exactly five canonical family-A authorities; every A13 helper declares `PARENT_COMPONENT_ID`, never `COMPONENT_ID`.
- Exact binding mode is `defeasible-justification-provenance-lineage-temporal-v7`.
- No production code is written before a failing behavior test is observed.
- A1–A12 protocol constants and serialized contracts are unchanged.
- No implicit wall clock; all semantics use explicit `TemporalContext`.
- Canonical set semantics are sorted and duplicate-free.
- All serialized restore paths fail closed on unknown fields, wrong protocol, digest mismatch, duplicate records, revision gaps, predecessor mismatch, or rebinding.
- Merge only with a frozen expected head after fresh focused and synthetic merge-state integration proof.

---

### Task 1: RED proof for missing A13 surface

**Files:**
- Create: `tests/test_truth_knowledge_hardening_wave13_defeaters.py`

**Interfaces:**
- Consumes: accepted A12 `KnowledgeJustificationRegistry`, `JustificationEpistemicJudge`, temporal/provenance primitives.
- Produces: executable contract requiring `knowledge_undercutter_truth`, `epistemic_defeasible_truth`, `verification_defeasible_truth`, and `assurance_defeasible_truth`.

- [ ] **Step 1: Write failing import/behavior test**

Create a realistic critical claim fixture with a live legacy support basis and evidence for an undercutter. Import the A13 modules and assert that a supported exact-bound undercutter defeats the legacy path and makes the target `UNKNOWN` when no alternative survives.

- [ ] **Step 2: Run focused Truth workflow**

Expected: compile of A1–A12 remains green; collection fails only because the first A13 module does not exist.

- [ ] **Step 3: Record exact RED run/head evidence**

The RED commit SHA and Actions run become part of the A13 candidate evidence chain.

---

### Task 2: Knowledge undercutter registry

**Files:**
- Create: `nolane/external_core/knowledge_undercutter_truth.py`
- Extend tests: `tests/test_truth_knowledge_hardening_wave13_defeaters.py`

**Interfaces:**
- Consumes: `KnowledgeLedger`, `KnowledgeClaim`, `KnowledgeJustificationRegistry`, `KnowledgeJustificationBasis`, `canonical_digest`.
- Produces: `JustificationUndercutterRevision`, `JustificationUndercutterRegistry`.

- [ ] **Step 1: Add RED tests**

Cover exact target-basis binding, non-empty attack basis, strict revision predecessor/gap law, target rebind rejection, target-claim self-parent rejection, combined dependency-cycle rejection, relevant-only projection, and restore domain/duplicate rejection.

- [ ] **Step 2: Implement immutable revision type**

The revision payload contains `protocol`, undercutter identity, target claim/digest, target justification ID/basis digest, revision/predecessor, evidence IDs, parent IDs, enabled, and canonical digest.

- [ ] **Step 3: Implement registry**

Registration resolves the target against `KnowledgeJustificationRegistry.effective_justifications()`, binds the exact basis digest, enforces lineage immutability, and validates the combined claim/undercutter dependency graph after tentative insertion.

- [ ] **Step 4: Implement projection/restore**

Projection returns only current revisions targeting claims in the requested set. Restore replays sorted revisions through the same public registration path.

- [ ] **Step 5: Run focused tests and preserve GREEN**

---

### Task 3: V7 defeasible epistemic scope

**Files:**
- Create: `nolane/external_core/epistemic_defeasible_truth.py`
- Extend tests: `tests/test_truth_knowledge_hardening_wave13_defeaters.py`

**Interfaces:**
- Consumes: all A9/A10 temporal/relation primitives, A11 provenance registry, A12 justification registry, A13 undercutter registry.
- Produces: `UndercutterStatus`, `DefeasibleJustificationStatus`, `DefeasibleTruthScope`, `DefeasibleEpistemicJudge`, `DEFEASIBLE_BINDING_MODE`.

- [ ] **Step 1: RED supported-undercutter behavior**

A supported undercutter with evidence `subject_id == undercutter_id` must turn a live supported target basis into `defeated`; with no clean alternative the claim becomes `UNKNOWN`.

- [ ] **Step 2: Implement undercutter evaluation**

Evaluate parents recursively, temporal evidence state, subject binding, and evidence polarity. Only exact-bound current target basis is attackable.

- [ ] **Step 3: RED alternative-survival behavior**

One defeated basis must not kill another clean supported OR branch.

- [ ] **Step 4: Implement v7 path aggregation**

Preserve intrinsic A12 status, apply supported/contradicted undercutters, then aggregate final path states according to the design.

- [ ] **Step 5: RED attack-state semantics**

Cover refuted undercutter leaves path clean, contradicted undercutter makes path `contested`, and unknown undercutter produces debt but cannot defeat support.

- [ ] **Step 6: Implement debt and contradiction semantics**

Keep A10 relation conflict behavior and emit undercutter debt with target risk awareness.

- [ ] **Step 7: RED fixed-point/staleness behavior**

Undercutter parent claim lineages must enter scope; unrelated undercutter revisions must not stale scope; relevant revisions must stale it.

- [ ] **Step 8: Implement combined fixed point and v7 projections**

Bind base Knowledge/Evidence, temporal projections, relation policy, A12 justification projection, A13 undercutter projection, provenance, assessments/statuses/debt/contradictions, context, and final digest.

- [ ] **Step 9: RED decision-source behavior**

Controller roots represented by live supported proof evidence or decisive undercutter evidence on supporting-lineage claims must enter `decision_source_ids`; dead/unrelated branch-only sources must not leak into the target decision trace.

- [ ] **Step 10: Implement contribution trace**

Trace target-reachable clean supported paths and their attached decisive undercutter evidence conservatively.

---

### Task 4: Exact v7 verification

**Files:**
- Create: `nolane/external_core/verification_defeasible_truth.py`
- Extend tests: `tests/test_truth_knowledge_hardening_wave13_verification.py`

**Interfaces:**
- Consumes: `DefeasibleTruthScope`, temporal Evidence, `SourceProvenanceRegistry`.
- Produces: `DefeasibleTruthVerificationReceipt`, `DefeasibleTruthVerificationCoverage`, `DefeasibleTruthVerificationLedger`.

- [ ] **Step 1: RED protocol-separation and origin-controller tests**

A v6 receipt must not deserialize/record as v7. A verifier controlled by a controller present in `decision_source_ids` must remain auditable but receive zero independence credit.

- [ ] **Step 2: Implement dedicated v7 receipt**

Exact-bind v7 scope digest, context digest/as-of, verifier, channel, evidence, provenance digest, pass/fail and v7 binding mode.

- [ ] **Step 3: Implement coverage/projection**

Retain invalid and negative receipts; derive canonical controller independence; exclude decision-origin controllers; keep projection exact to scope/context.

- [ ] **Step 4: Run focused verification tests**

---

### Task 5: Risk-sensitive v7 assurance

**Files:**
- Create: `nolane/external_core/assurance_defeasible_truth.py`
- Extend tests: `tests/test_truth_knowledge_hardening_wave13_assurance.py`

**Interfaces:**
- Consumes: full live v7 state and v7 verification ledger.
- Produces: `DefeasibleTruthClosureCertificate`, `DefeasibleTruthAssuranceGate`.

- [ ] **Step 1: RED closure tests**

Cover: defeated sole basis blocks closure; clean alternative survives defeated branch; supporting-lineage conflict blocks; dead/defeated branch parent does not veto clean alternative; CRITICAL unresolved-underutter debt blocks; sufficient clean verification closes.

- [ ] **Step 2: Implement dedicated v7 certificate/gate**

Keep risk thresholds 1/1, 2/2, 3/3. Derive supporting lineage only through final `supported` paths. Recompute complete live v7 state during validation.

- [ ] **Step 3: RED stale-certificate tests**

Relevant undercutter revision must invalidate old certificate; unrelated revision must not.

- [ ] **Step 4: Implement exact validation**

No serialized v7 certificate is self-authenticating.

---

### Task 6: Authority and compatibility hardening

**Files:**
- Create: `tests/test_truth_knowledge_hardening_wave13_authority.py`
- Modify: `.github/workflows/truth-knowledge-a.yml`

**Interfaces:**
- Produces: repository-level guarantees that A13 remains a sidecar protocol only.

- [ ] **Step 1: RED authority tests**

Assert all four A13 modules expose the expected `PARENT_COMPONENT_ID`, expose no `COMPONENT_ID`, and use exact v7 protocol/binding separation.

- [ ] **Step 2: Add workflow paths and py_compile entries**

Add all A13 production modules to push/PR filters and compile step; focused tests continue using `tests/test_truth_knowledge_*.py`.

- [ ] **Step 3: Compatibility test**

With no undercutters, compare v7 and accepted v6 target dispositions, final path semantics, supporting lineage, and controller-origin behavior.

- [ ] **Step 4: Full focused regression**

Run all Truth/Knowledge tests and repository audit.

---

### Task 7: Candidate documentation and freeze

**Files:**
- Modify: `CURRENT/TRUTH_KNOWLEDGE.md`

- [ ] **Step 1: Document A13 as candidate, not accepted**

Describe v7 undercutter law, fixed point, decision-source independence, verification/assurance, compatibility, RED/GREEN evidence, and exact candidate head.

- [ ] **Step 2: Freeze candidate head**

No semantic change after this point unless exact-head CI exposes a defect.

---

### Task 8: Exact-head integration and production merge

- [ ] **Step 1: Require focused Truth/Knowledge push run GREEN on Python 3.11 and 3.13**
- [ ] **Step 2: Open PR and verify intended-only changed files**
- [ ] **Step 3: Verify zero reviews/unresolved review threads or address genuine blockers**
- [ ] **Step 4: Require full Refoundation Epoch 0 GREEN on the PR synthetic merge SHA for Python 3.11 and 3.13**
- [ ] **Step 5: Re-read `main`; if it advanced, verify the new merge state rather than trusting stale branch CI**
- [ ] **Step 6: Merge with `expected_head_sha=<frozen A13 candidate>` and merge method `merge`**
- [ ] **Step 7: Verify production merge parents contain exact pre-merge main and exact frozen A13 candidate**

---

### Task 9: Separate A13 acceptance seal

**Files:**
- Modify only: `CURRENT/TRUTH_KNOWLEDGE.md`

- [ ] **Step 1: Branch from exact production merge**
- [ ] **Step 2: Change status to A1–A13 accepted and record exact candidate, focused CI, merge-state Refoundation, production PR/merge, and proof**
- [ ] **Step 3: Verify seal diff is exactly one documentation file**
- [ ] **Step 4: Require fresh Truth/Knowledge and full Refoundation synthetic merge-state proof**
- [ ] **Step 5: Merge seal with expected-head protection**
- [ ] **Step 6: Verify final `main` and canonical status line**
