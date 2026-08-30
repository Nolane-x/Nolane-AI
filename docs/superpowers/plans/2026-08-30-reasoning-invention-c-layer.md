# Reasoning / Invention C-Layer Implementation Plan

**Goal:** Introduce a canonical, stateless Reasoning/Invention protocol spine across Cognitive Library, Candidate Synthesis, Causal, Experimentation, Capability Acquisition and Transfer/Meta without transferring write or promotion authority between those components.

**Architecture:** Add `nolane.external_core.reasoning_invention` as immutable protocol/data semantics only. It converts discovery evidence into falsifiable invention hypotheses and verification plans, carries independent challenge receipts, computes deterministic Pareto frontiers, and emits capability-gap or transfer-intent envelopes. Existing C authorities remain independent. No direct mutation API is exposed.

**Tech stack:** Python 3.11/3.13, dataclasses/enums, canonical SHA-256 state identity through `nolane.core.canonical_digest`, pytest, GitHub Actions Refoundation gate.

---

## Task 1 — RED: declaration contract

**Files:**
- Create: `tests/test_refoundation_post_epoch0_reasoning_invention.py`

**RED behavior:**
- assert canonical module `nolane.external_core.reasoning_invention` exists;
- assert it declares `external.reasoning_invention` v0.0.1;
- no production implementation exists yet.

Run hosted Refoundation CI and confirm failure is caused by the missing canonical module/capability, not baseline regressions.

## Task 2 — GREEN declaration / RED behavior

**Files:**
- Create: `nolane/external_core/reasoning_invention.py`
- Extend: `tests/test_refoundation_post_epoch0_reasoning_invention.py`

First add only component constants and a minimal empty public surface to turn the declaration RED green. Then add behavior tests before implementing behavior.

Behavior RED contracts:

1. `ReasoningEvidenceRef` rejects empty IDs and normalizes phase/source/witness semantics.
2. `VerificationPlan` requires perturbation, negative-control, ablation and stop-condition sets; all numeric fields are finite and cost is positive.
3. `InventionHypothesis` accepts discovery anchors only and binds assumptions, generalized variables, invariants, predicted deltas and the exact plan.
4. Same semantic input yields same IDs; set-like provenance ordering is invariant.
5. `InventionAssessment` exposes bounded multi-objective dimensions and deterministic Pareto dominance.
6. `pareto_frontier` returns all and only non-dominated candidates in canonical identity order.
7. `HypothesisChallenge` accepts independent-challenge evidence only; VERIFIED requires causal/experiment support.
8. `CapabilityGap` binds exact library digest, insufficiency evidence, acceptance tests and candidate ID without importing or mutating Capability Acquisition.
9. `TransferIntent` is source/target bound and requires invariants plus trials without importing or mutating Transfer/Meta.
10. `ReasoningInventionReceipt` aggregates only canonical IDs and cannot represent promotion/installation/reuse authority.
11. Every persisted object round-trips canonically and rejects tampered derived IDs/non-canonical state.
12. The module has no reverse import into mutable C governors or Assurance.

Observe hosted RED from missing behavior APIs.

## Task 3 — GREEN: immutable protocol implementation

Implement only the behavior required above:

- `EvidencePhase`, `ChallengeVerdict`, `CapabilityKind` protocol enums;
- strict helpers for IDs, finite scores, normalized sets and canonical state;
- `ReasoningEvidenceRef`;
- `VerificationPlan` with descriptive information-efficiency property;
- `PredictedDelta`;
- `InventionHypothesis`;
- `InventionAssessment`;
- `InventionCandidate`;
- `dominates` and `pareto_frontier`;
- `HypothesisChallenge`;
- `CapabilityGap`;
- `TransferIntent`;
- `ReasoningInventionReceipt`;
- exact `to_state` / `from_state` and derived content identity validation.

Do not import `CapabilityAcquisitionGovernor`, `TransferMetaGovernor`, `AssuranceControlPlane` or any mutable ledger. Refer to outputs from existing authorities by exact IDs/digests only.

## Task 4 — Canonical metadata declaration

**Files:**
- Modify: `nolane/metadata/_component_specs.py`
- Modify: `nolane/metadata/component_versions.py`
- Modify: `nolane/metadata/implementation_status.py`
- Modify: `CURRENT/EXTERNAL_CORE.md`

Declare `external.reasoning_invention` v0.0.1 as canonical-native with dependencies on `external.cognitive_library`, `external.candidate_synthesis`, `external.causal`, `external.experimentation` and `external.evidence`. Do **not** give it Capability Acquisition, Transfer/Meta or Assurance write dependencies; those are downstream intent consumers, not owned authorities.

Update canonical architecture documentation to explain C-layer cycle and authority separation.

If repository audit/dossier fixtures are mechanically coupled to component count, update only the exact generated/acceptance surfaces required by fresh audit evidence; never weaken assertions.

## Task 5 — Focused verification

Run/inspect hosted CI for the feature branch:

- focused Reasoning/Invention contracts on Python 3.11 and 3.13;
- accepted Refoundation suite;
- canonical namespace compilation;
- repository audit/dossier freshness;
- broad regressions;
- frozen Neural verifier.

Any failure must be classified as implementation defect, stale accepted metadata, or unrelated baseline issue before editing.

## Task 6 — Hardening

Add adversarial tests before fixes for any defects found by full CI, especially:

- bool-as-int numeric smuggling;
- NaN/Infinity state;
- duplicate IDs after normalization;
- forged derived IDs;
- label changes affecting semantic identity;
- challenge evidence phase confusion;
- VERIFIED without independent causal/experimental support;
- caller-order dependence in Pareto frontier;
- equal assessment vectors;
- source==target transfer;
- empty invariants/trials;
- mutable-object leakage into protocol state.

Re-run focused and full gates after each hardening change.

## Task 7 — PR and merge gate

Create/update a PR against `main` with:

- exact parent/head SHAs;
- RED evidence;
- GREEN evidence;
- authority boundary;
- changed-file census;
- current limitations / roadmap C2-C7.

Do not merge until exact final head is hosted-green on the canonical Python matrix. If green, leave the branch and PR in a reviewable state unless the user's standing repo instruction explicitly authorizes direct merge.