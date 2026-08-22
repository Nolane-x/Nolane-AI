# Verification & Security Part VIII Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans or subagent-driven-development. Test-first RED contracts precede production modules.

**Goal:** Make Verification and Security independent, identity-grounded falsification authorities with fresh evidence, blocking receipts, auditable Central override and production promotion gates.

**Architecture:** Add assurance profiles, immutable subject/challenge/evidence ledgers and an `AssuranceControlPlane` over existing `AuthorityGraph`, `ArtifactStore`, `EventLedger`, `VerificationAuthority` and `SkillEvolutionEngine`. Keep low-level Part-I promotion primitives backward compatible while adding an assured production wrapper.

**Spec:** `docs/superpowers/specs/2026-08-22-verification-security-part8-design.md`

## Global constraints

- Exactly 9 assurance identities: 5 verification + 4 security.
- Self-verification never authorizes producer work.
- Verification/Security can block Chief- or Central-produced artifact revisions.
- Central override remains an override, never a pass.
- Evidence is version/epoch/sandbox grounded.
- False accepts/regressions fail closed.
- Promotion wrapper requires heldout + cross-version + multiple independent identities.
- Both Chiefs are direct falsification/adversarial workers.
- No automatic merge or promotion from an ordinary assurance decision.
- Parts I–VII remain regression-clean.

### Task 1 — Profiles and routing
**Create:** `cogcoder/organization/assurance_profiles.py`
**Test:** `tests/test_coding_agi_assurance_profiles.py`

- [ ] RED exact 9 profiles, 5 verification/4 security, non-identical domains.
- [ ] RED deterministic routing for unit/property, integration/E2E, spec/acceptance, fuzz/regression, threat, supply-chain, adversarial and cross-Chief work.
- [ ] RED profile serialization reads current neural version from AgentRegistry.
- [ ] GREEN implement `AssuranceDomain`, profile/work request/assignment receipt/registry.

### Task 2 — Subjects, challenge cases and evidence
**Create:** `cogcoder/organization/assurance_evidence.py`
**Test:** `tests/test_coding_agi_assurance_evidence.py`

- [ ] RED immutable subject registration and digest.
- [ ] RED challenge case belongs to subject and creator must be assurance identity.
- [ ] RED evidence rejects self-producer verifier, wrong verifier region/domain, stale version/epoch and missing sandbox digest.
- [ ] RED evidence preserves false-accept/regression counters and cannot be rebound.
- [ ] GREEN implement subject/case/evidence ledgers with canonical counters/restore.

### Task 3 — Policies, decisions and blocking
**Create:** `cogcoder/organization/assurance.py`
**Test:** `tests/test_coding_agi_assurance_decisions.py`
**Test:** `tests/test_coding_agi_assurance_blocking.py`

- [ ] RED policy required-domain omissions reject.
- [ ] RED failed/false-accept/regression evidence rejects.
- [ ] RED clean complete evidence verifies.
- [ ] RED Verification/Security can create blocking receipts for Chief- or Central-originated subject artifacts.
- [ ] GREEN implement policy table, `AssuranceDecision`, `BlockingReceipt`, recomputed assessment.

### Task 4 — Central override semantics
**Test:** `tests/test_coding_agi_assurance_override.py`
**Modify:** `cogcoder/organization/assurance.py`

- [ ] RED Central override requires explicit reason/evidence.
- [ ] RED override references original block/decision and AuthorityGraph override.
- [ ] RED effective disposition becomes `OVERRIDDEN`; original decision remains rejected/blocked.
- [ ] RED no path relabels rejected evidence as passed.
- [ ] GREEN implement `AssuranceOverrideReceipt` and effective disposition query.

### Task 5 — Promotion assurance wrapper
**Test:** `tests/test_coding_agi_assurance_promotion.py`
**Modify:** `cogcoder/organization/assurance.py`

- [ ] RED missing heldout digest rejects promotion authorization.
- [ ] RED missing cross-version predecessor ref rejects.
- [ ] RED one verifier identity is insufficient.
- [ ] RED false accepts/regressions reject.
- [ ] RED clean multi-verifier fresh heldout/cross-version evidence authorizes a receipt.
- [ ] GREEN implement `PromotionAssuranceReceipt` and a wrapper that can invoke existing low-level neural promotion only after authorization.

### Task 6 — Direct Chiefs and learning
**Test:** `tests/test_coding_agi_assurance_direct_work.py`
**Test:** `tests/test_coding_agi_assurance_learning.py`

- [ ] RED Verification Chief personally creates falsification challenge/evidence and blocks a Chief/Central subject when falsified.
- [ ] RED Security Chief personally creates threat/adversarial challenge/evidence and blocks a security regression.
- [ ] RED both complete ordinary Chief tasks with challenge/evidence artifacts.
- [ ] RED learned assurance technique remains `SkillScope.CANDIDATE` until normal promotion.
- [ ] GREEN implement minimal personal-skill and direct-work support using existing runtime/task/artifact paths.

### Task 7 — Runtime, context, snapshot and CI
**Modify:** `cogcoder/organization/runtime.py`
**Modify:** `cogcoder/organization/context.py`
**Test:** `tests/test_coding_agi_assurance_snapshot.py`
**Test:** `tests/test_coding_agi_assurance_context.py`
**Create:** `.github/workflows/coding-agi-assurance-part8.yml`

- [ ] RED snapshot round-trips subjects/cases/evidence/decisions/blocks/overrides/promotion receipts exactly.
- [ ] RED verification/security agents receive `assurance-state`; unrelated regions do not receive full assurance private state.
- [ ] Integrate runtime after UI/Debugging and before Context/Central; preserve older snapshot defaults.
- [ ] Python 3.11/3.13 workflow runs Part VIII plus Parts I–VII regressions.
- [ ] Capture valid RED then exact-head GREEN before merge.

## Self-review

Every Issue #136 acceptance gate maps to an explicit contract. AuthorityGraph remains canonical for blocks/overrides. Existing low-level promotion primitives remain backward-compatible but Part-VIII production orchestration adds stronger gates. No TODO/TBD placeholders and no infallibility/security-equivalence claim.
