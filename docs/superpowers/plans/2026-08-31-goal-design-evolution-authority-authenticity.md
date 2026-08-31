# Goal/Design Evolution Authority Authenticity Implementation Plan

> Execute with TDD. Preserve historical authority identities; do not mutate production state before verifier checks complete.

**Goal:** Replace self-asserted Goal/Design evolution `authority_ref` strings with verifier-issued, transition-bound capability authorization while preserving truthful migration of historical state.

**Architecture:** Freeze the accepted v0.1 evolution protocol and v0.2 runtime as private compatibility layers. Add a provider-neutral capability registry/verifier with externally supplied trust roots, attenuating delegation, verifier-clock temporal checks, revocation, content-addressed authorization proofs, and independent state verification. Layer public evolution protocol v0.2 and runtime v0.3 above the frozen compatibility surfaces.

**Tech stack:** Python 3.11+, frozen dataclasses, deterministic `stable_digest`, pytest, GitHub Actions hosted matrices.

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

1. Implement immutable content-addressed `GoalIntegrityEvolutionGrant`.
2. Implement immutable transition-bound `GoalIntegrityEvolutionAuthorizationProof`.
3. Implement `GoalIntegrityEvolutionAuthorityVerifier` with externally supplied trusted root issuers and injected clock.
4. Enforce root trust, delegation attenuation, bounded depth, goal/action scope, validity windows, verifier-time issuance, revocation, and ancestor revocation.
5. Implement deterministic state export/import with digest and full semantic replay; never restore trust roots from serialized state.
6. Run focused tests until GREEN.

### Task 4: Upgrade public evolution receipt protocol

**Files:**
- Modify: `nolane/external_core/goal_design_integrity_evolution.py`
- Test: `tests/test_goal_design_integrity_evolution_authenticity.py`
- Test: `tests/test_goal_design_integrity_evolution_authority.py`

1. Layer v0.2 over frozen v0.1 definitions where safe.
2. Add explicit schema-aware authority scheme for newly minted receipts while preserving v1 identity verification during historical restore.
3. Make new receipt minting require a verifier-issued authorization proof reference.
4. Preserve deterministic transition delta and nested identity checks.

### Task 5: Upgrade runtime to verifier-backed v0.3

**Files:**
- Modify: `nolane/external_core/goal_design_integrity_runtime.py`
- Test: `tests/test_goal_design_integrity_evolution_authenticity.py`
- Test: `tests/test_goal_design_integrity_evolution_authority.py`
- Test: `tests/test_goal_design_integrity_runtime_restore_authority.py`

1. Subclass the frozen v0.2 runtime.
2. Inject or configure an evolution authority verifier without creating implicit trust.
3. For new revisions, perform receipt structural verification, then verifier proof verification, then state mutation.
4. Advance runtime state to schema v3.
5. Migrate historical v1/v2 revisions to explicit non-fabricated trust labels; only new verifier-backed revisions receive `verified_capability_authority`.
6. On v3 restore, re-verify every authorization proof before publishing temporary state atomically.

### Task 6: Hosted acceptance and integration closure

**Files:** no production changes unless verification discovers a defect.

1. Run hosted Goal Design Coherence Plane on Python 3.11 and 3.12; require zero failures.
2. Run/inspect Refoundation Epoch 0 and broader regressions triggered by the PR.
3. Compare exact base -> head and confirm payload contains only intended D files/docs/tests.
4. Classify any historical frozen-boundary workflow failures against exact payload before treating them as blockers.
5. Update PR acceptance record with RED -> GREEN evidence.
6. Merge only with `expected_head_sha` after fresh verification.
7. Verify `main` points to the merge commit and inspect fresh post-merge Goal Design/R1.9/R2.0i push workflows.
