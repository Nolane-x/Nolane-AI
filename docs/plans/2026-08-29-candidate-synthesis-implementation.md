# Candidate Synthesis v0.0.1 Implementation Plan

> Execution rule: `CURRENT/` remains architectural authority. This plan is implementation guidance and must not weaken existing Refoundation, Assurance, Cognitive Library, Capability Acquisition, or frozen Neural contracts.

**Goal:** Add a bounded canonical candidate-generation authority that can synthesize a real learned-abstraction proposal from existing canonical abstractions while remaining stateless and unable to admit, probation, promote, persist, or self-assure the result.

**Architecture:** `external.candidate_synthesis` consumes canonical Cognitive Library state plus provenance references, generates immutable `CapabilityCandidate` proposals, and returns a content-addressed `SynthesisReceipt`. Capability Acquisition remains the only lifecycle governor downstream. v0.0.1 implements ordered unary learned-abstraction composition only.

**Tech stack:** Python 3.11/3.13, pytest, canonical SHA-256 digest/state contracts, GitHub Actions, repository audit, frozen Neural R2.3 verifier.

---

## Task 1 — RED/GREEN: Canonical component declaration

**Files:**
- Create: `tests/test_post_epoch0_candidate_synthesis.py`
- Create: `nolane/external_core/candidate_synthesis.py`
- Modify: `nolane/metadata/_component_specs.py`
- Modify: `nolane/metadata/component_versions.py`
- Modify: `nolane/metadata/implementation_status.py`

**RED:** Require `external.candidate_synthesis` v0.0.1 to exist as a canonical native component with the exact canonical module and with no historical runtime source claim.

**GREEN:** Add only component constants/metadata and an empty public surface sufficient for the declaration contract. Do not implement synthesis behavior yet.

## Task 2 — RED: Proposal/evidence/mutation contracts

Extend `tests/test_post_epoch0_candidate_synthesis.py` before adding behavior.

Contracts:
1. ordered unary source composition creates a new `CapabilityCandidate` whose template is generated from `AbstractionCall` nodes;
2. same semantic request yields same synthesis ID and candidate ID;
3. set-like provenance ordering is identity-invariant;
4. source ordering is semantic and may change candidate identity;
5. zero budget abstains without candidate generation;
6. missing/duplicate/non-unary sources fail closed;
7. discovery evidence is allowed, challenge/final-assurance evidence is forbidden during generation;
8. semantic duplicates/already-installed generated abstractions abstain;
9. synthesis leaves Cognitive Library digest unchanged;
10. synthesis leaves Capability Acquisition governor unchanged because it receives no governor authority;
11. only an explicit caller `admit(candidate)` creates downstream `CANDIDATE` state;
12. synthesis cannot self-transition to probation;
13. request/receipt state round-trips canonically and tampering is rejected.

Observe hosted RED caused by missing behavior API, not by syntax/import accidents.

## Task 3 — GREEN: Minimal deterministic synthesis

Implement only what the RED suite requires:
- `EvidencePhase` / immutable evidence provenance refs;
- immutable `SynthesisRequest` with canonical normalization;
- immutable `SynthesisReceipt` with content-derived identity and state round-trip;
- `CandidateSynthesisEngine.synthesize_learned_abstraction_composition`;
- ordered composition of unary abstractions using `TemplateParam(0)` and nested `AbstractionCall` nodes;
- deterministic support-task union and bounded cost accounting;
- conversion through `CapabilityCandidate.for_learned_abstraction`;
- fail-closed abstention reasons;
- before/after Cognitive Library digest guard;
- no acquisition/assurance mutation APIs.

No executable operator invention, no search explosion, no persistence.

## Task 4 — Metadata/audit/docs closure

**Files:**
- Update: `CURRENT/EXTERNAL_CORE.md`
- Regenerate repository audit projections if required by canonical audit.
- Keep `CURRENT/NATIVE_DEBT.*` semantics unchanged except for generated inventory consequences implied by the new canonical component (expected: no new migration debt).

Verify the component graph has no dependency cycle and the implementation ledger classifies the new component as `canonical_native` v0.0.1.

## Task 5 — Verification and merge gate

Focused verification:
- `python -m pytest -q tests/test_post_epoch0_candidate_synthesis.py`

Repository verification:
- `python -m compileall -q cogcoder/organization cogcoder/refoundation nolane`
- `python -m nolane.ai.materialize --check`
- `python -m nolane.repository.audit --check`
- `python -m pytest -q tests/test_refoundation_*.py`
- broad organization/campaign/execution regressions from the canonical Refoundation workflow
- `python model/neural-r2.3/scripts/verify_neural_r23.py`

Open a PR only after focused GREEN. Remove any temporary TDD carrier before final merge. Require fresh hosted Python 3.11 and 3.13 GREEN evidence on the exact final code head before merge.