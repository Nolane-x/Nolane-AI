# Goal/Design Evolution Authority Authenticity Implementation Plan

> Execute with TDD. Preserve historical authority identities; do not mutate production state before verifier checks complete.

**Goal:** Replace self-asserted Goal/Design evolution `authority_ref` strings with verifier-issued, transition-bound capability authorization while preserving truthful migration of historical state.

**Architecture:** Freeze the accepted v0.1 evolution protocol and v0.2 runtime as private compatibility layers. Add a provider-neutral capability registry/verifier with externally supplied trust roots, attenuating delegation, verifier-clock temporal checks, monotonic revocation, content-addressed authorization proofs, authenticated state, and an out-of-band rollback-resistant latest-state checkpoint. Layer public evolution protocol v0.2 and runtime v0.3 above the frozen compatibility surfaces.

**Tech stack:** Python 3.11+, frozen dataclasses, deterministic `stable_digest`, HMAC-SHA256, pytest, GitHub Actions hosted matrices.

---

### Task 1: Prove the self-asserted authority vulnerability

**Files:**
- Create: `tests/test_goal_design_integrity_evolution_authenticity.py`

1. Add a regression showing a valid content-addressed evolution receipt with an invented `authority_ref` is currently accepted.
2. Add RED contracts for exact proof binding, scope, time, revocation, delegation attenuation, state tamper, and migration semantics.
3. Push test-only commit and obtain hosted RED from `python -m pytest -q tests/test_goal_design*.py`.

### Task 2: Freeze accepted compatibility surfaces

**Files:**
- Create: `nolane/external_core/_goal_design_integrity_evolution_v01.py`
- Create: `nolane/external_core/_goal_design_integrity_runtime_v02.py`

1. Copy accepted public v0.1 evolution implementation byte-for-source semantics into the private v01 module.
2. Copy accepted public v0.2 runtime semantics into the private v02 module, changing only its evolution import to the frozen v01 module.
3. Verify frozen modules compile and historical tests remain behaviorally equivalent.

### Task 3: Implement capability authority verifier

**Files:**
- Create: `nolane/external_core/goal_design_integrity_evolution_authority.py`
- Test: `tests/test_goal_design_integrity_evolution_authenticity.py`
- Test: `tests/test_goal_design_integrity_evolution_live_revocation.py`

1. Implement immutable content-addressed `GoalIntegrityEvolutionGrant`.
2. Implement immutable transition-bound `GoalIntegrityEvolutionAuthorizationProof`.
3. Implement `GoalIntegrityEvolutionAuthorityVerifier` with externally supplied trusted root issuers and injected clock.
4. Enforce root trust, delegation attenuation, bounded depth, goal/action scope, validity windows, verifier-time issuance, monotonic first-revocation semantics, ancestor revocation, and permanent fail-closed live revocation even if the verifier clock rolls backward.
5. Separate historical proof verification from live authorization so later revocation closes future mutations without corrupting already committed history.
6. Implement deterministic authority-state export with structural digest and keyed authenticator; never restore trust roots or key material from serialized state.
7. Require an out-of-band `expected_state_digest` for restore. Treat keyed authentication as authenticity, not freshness, and reject an older correctly signed snapshot when it does not match the rollback-resistant external checkpoint.
8. Replay-validate restored grants, delegation structure, revocations, and proofs only after digest, authenticator, and freshness-checkpoint verification succeed.
9. Run focused tests until GREEN.

### Task 4: Upgrade public evolution receipt protocol

**Files:**
- Modify: `nolane/external_core/goal_design_integrity_evolution.py`
- Test: `tests/test_goal_design_integrity_evolution_authenticity.py`
- Test: `tests/test_goal_design_integrity_evolution_authority.py`

1. Layer v0.2 over frozen v0.1 definitions where safe.
2. Preserve v1 receipt identity verification during historical restore.
3. Make new verified receipt minting bind a verifier-issued authorization proof reference.
4. Preserve deterministic transition delta and nested identity checks.
5. Do not infer authority from the dataclass shape of a supplied proof; runtime must resolve the proof ID through the injected verifier.

### Task 5: Upgrade runtime to verifier-backed v0.3

**Files:**
- Modify: `nolane/external_core/goal_design_integrity_runtime.py`
- Test: `tests/test_goal_design_integrity_evolution_authenticity.py`
- Test: `tests/test_goal_design_integrity_evolution_authority.py`
- Test: `tests/test_goal_design_integrity_runtime_restore_authority.py`
- Test: `tests/test_goal_design_integrity_runtime.py`

1. Subclass the frozen v0.2 runtime.
2. Inject or configure an evolution authority verifier without creating implicit trust.
3. For new revisions, perform receipt structural verification, then live verifier proof verification, then state mutation.
4. Reject stockpiled pre-revocation proofs for new mutations and reject authority revival through clock rollback.
5. Advance runtime state to schema v3.
6. Migrate historical v1/v2 revisions to explicit non-fabricated trust labels; only verifier-backed revisions receive `verified_capability_authority`.
7. On v3 restore, re-verify every authorization proof historically before publishing temporary state atomically; do not require later-revoked authority to still be live for already committed history.

### Task 6: Hosted acceptance and integration closure

**Files:** no production changes unless verification discovers a defect.

1. Run hosted Goal Design Coherence Plane on Python 3.11 and 3.12; require zero failures.
2. Run/inspect Refoundation Epoch 0, R1.9 Integrity, R2.0i Integrity, and broader regressions triggered by the PR.
3. Compare exact base -> head and confirm payload contains only intended D files/docs/tests.
4. Classify historical frozen-boundary workflow failures by their exact mismatched path before treating them as blockers; do not conflate stale historical locks with Goal/Design behavior regressions.
5. Record RED evidence for the self-asserted authority and live-revocation vulnerabilities, and final GREEN evidence for all authority, rollback-checkpoint, migration, and restore cases.
6. Update PR acceptance record with exact head, synthetic merge SHA, Python test counts, Refoundation/integrity results, and non-blocking historical-boundary classifications.
7. Race-guard `main`; if it moved, rebuild and re-prove the exact union rather than merging stale evidence.
8. Merge only with `expected_head_sha` after fresh verification.
9. Verify `main` points to the merge commit and inspect fresh post-merge Goal Design/Refoundation/R1.9/R2.0i workflows on the actual main state.
