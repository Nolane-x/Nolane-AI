# Part XIV — Ephemeral Specialist Foundry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a governed optional Foundry that creates task-scoped temporary specialists without granting them permanent identity, authority, memory, or self-promotion privileges.

**Architecture:** Add focused Foundry modules above accepted Parts VIII, XII, and XIII. Temporary identities stay outside `AgentRegistry`; raw artifacts keep ephemeral producer provenance; a permanent sponsor bridge is the only Part-VIII assurance subject; reusable skills flow through Part XII; parent-task lineage flows through Part XIII. Part XIV runtime integration is a thin façade over the accepted Part-XIII runtime.

**Tech Stack:** Python 3.11/3.13, dataclasses/enums, existing Nolane organization primitives, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-22-ephemeral-specialist-foundry-part14-design.md`

## Global Constraints
- Permanent organization remains exactly 67 identities; ephemeral identities never enter `AgentRegistry`.
- Ephemeral workers never own authoritative artifacts and never write active permanent `MemoryFabric` directly.
- Only `nolane.central` or an authorized Regional Chief may approve spawning.
- First-generation Foundry ceilings: 12 active ephemeral workers organization-wide, 4 per team, 3 active teams per sponsor.
- Spawn budgets must have positive compute/tool/core/lifetime values.
- Raw output remains authored by the ephemeral ID; Part VIII verifies only a permanent sponsor-produced `foundry-handoff` bridge artifact.
- Engineering-authorizing handoff requires Part-VIII `VERIFIED`; `OVERRIDDEN` is not independent verification.
- Skill distillation produces only a permanent-owner `SkillScope.CANDIDATE`; Part XII owns promotion.
- Parent TaskGraph/Part-XIII lease lineage is authoritative; stale lease epoch blocks handoff/distillation.
- Destroyed scratch content must never reappear after snapshot restore.
- Zero-ephemeral runtime must preserve all Parts I–XIII behavior.

---

### Task 1: Profiles, spawn requests, and permanent-authority boundary

**Files:**
- Create: `cogcoder/organization/foundry_profiles.py`
- Create: `tests/test_coding_agi_foundry_profiles_spawn.py`

**Interfaces:**
- Produces `FoundryTemplate`, `SpawnRequest`, `EphemeralIdentityManifest`, `FoundryProfileRegistry`.
- `request(...)` creates immutable REQUESTED spawn requests.
- `approve(request_id, actor_agent_id)` accepts only Central or authorized Regional Chief.
- `instantiate(request_id, current_token, parent_lease_id=None, parent_lease_epoch=None)` creates a content-addressed temporary manifest outside `AgentRegistry`.

- [ ] Write RED tests for five templates, 67/67 permanent identity preservation, Central/Chief authority, wrong-region rejection, and tool/core/artifact envelope escalation.
- [ ] Run RED and confirm failure is missing Part-XIV modules, not an old regression.
- [ ] Implement immutable profile/spawn model with `canonical_digest` and permanent-registry sponsor validation.
- [ ] Run GREEN and commit.

### Task 2: Hard resource governance and concurrency

**Files:**
- Create: `cogcoder/organization/foundry_resources.py`
- Create: `tests/test_coding_agi_foundry_resources.py`

**Interfaces:**
- Produces `FoundryBudget`, `FoundryResourceKind`, `ResourceUsageReceipt`, `FoundryResourceGovernor`.
- `register_manifest(ephemeral_id, team_id, sponsor_agent_id, budget)` binds immutable budget.
- `consume(ephemeral_id, resource_kind, units, actor_ephemeral_id)` fails closed on actor mismatch or exhaustion.
- `reserve_active(ephemeral_id)` enforces 12 organization / 4 team / 3 sponsor-team limits.

- [ ] Write RED tests for positive budgets, exact counters, compute/tool/core exhaustion, identity binding, all three concurrency ceilings, deterministic release and snapshot round-trip.
- [ ] Run RED.
- [ ] Implement content-addressed usage receipts and counters.
- [ ] Run GREEN and commit.

### Task 3: Lifecycle and isolated scratch vault

**Files:**
- Create: `cogcoder/organization/foundry_lifecycle.py`
- Create: `cogcoder/organization/foundry_memory.py`
- Create: `tests/test_coding_agi_foundry_lifecycle_memory.py`

**Interfaces:**
- Produces `FoundryStatus`, `FoundryLifecycleReceipt`, `FoundryLifecycleLedger`.
- Produces `ScratchDisposition`, `ScratchEntry`, `ScratchTombstone`, `EphemeralScratchVault`.
- Lifecycle only accepts declared forward transitions; terminal states are non-reactivatable.
- Scratch writes/reads require the exact ephemeral identity.
- `DESTROY` retains only tombstone metadata/digest; `ARCHIVE_QUARANTINE` never enters permanent memory.

- [ ] Write RED lifecycle and scratch isolation/destruction tests.
- [ ] Run RED.
- [ ] Implement state machine and vault.
- [ ] Run GREEN and commit.

### Task 4: Raw output provenance, independent verification, and sponsor assurance bridge

**Files:**
- Create: `cogcoder/organization/foundry_evidence.py`
- Create: `tests/test_coding_agi_foundry_evidence_authority.py`

**Interfaces:**
- Produces `FoundryOutputReceipt`, `FoundryVerificationReceipt`, `FoundryHandoffReceipt`.
- `emit_output()` stores durable raw artifact with the ephemeral producer ID.
- `record_verification()` stores permanent external verification; sponsor-only evidence remains non-independent.
- `prepare_handoff()` creates a content-addressed `foundry-handoff` artifact produced by the permanent sponsor and binding raw artifact ID/digest, ephemeral ID, lease lineage, target, verification evidence and limitations.
- The caller registers/assesses that bridge through existing Part VIII.
- `authorize_handoff(handoff_id, assurance_decision_id)` checks that the decision subject points to the bridge artifact and `assurance.effective_disposition(subject_id) is VERIFIED`.

- [ ] Write RED tests proving raw artifact producer stays ephemeral and survives retirement.
- [ ] Prove ephemeral ID cannot own/write authoritative artifacts.
- [ ] Prove clean verifier is permanent/external and sponsor-only verification is insufficient.
- [ ] Prove Part VIII cannot register raw ephemeral artifact directly, but can register the permanent sponsor bridge.
- [ ] Prove bridge `VERIFIED` authorizes while bridge `OVERRIDDEN` does not.
- [ ] Run RED.
- [ ] Implement receipts and bridge flow without modifying Part VIII.
- [ ] Run GREEN and commit.

### Task 5: Foundry orchestration, stale lease containment, skill distillation, benefit measurement

**Files:**
- Create: `cogcoder/organization/foundry.py`
- Create: `tests/test_coding_agi_foundry_control_distillation.py`
- Create: `tests/test_coding_agi_foundry_benefit.py`

**Interfaces:**
- `FoundryControlPlane` composes registry/tasks/coordination/artifacts/assurance/evolution/individual_evolution plus Tasks 1–4 modules.
- `distill_skill(handoff_id, target_agent_id, name, body)` calls `SkillEvolutionEngine.propose()` only after authorized bridge, clean independent verification, current parent lease, success state, and target ownership checks.
- `FoundryBenefitObservation` / `FoundryBenefitAssessment` compare same task/regime/matched budget only.

- [ ] Write RED stale-parent-lease tests: instantiate on epoch N, revoke/reassign, prove old output cannot authorize or distill.
- [ ] Write RED skill tests: result scope is `CANDIDATE`, permanent target is owner, failed/quarantined work cannot distill, Part XII remains promotion authority.
- [ ] Write RED matched-budget tests: same regime + higher score + no worse false accepts/regressions + within budget => improved; mismatched regime/budget => not improved/incomparable.
- [ ] Run RED.
- [ ] Implement orchestration and benefit ledger.
- [ ] Run GREEN and commit.

### Task 6: Runtime façade and exact snapshot compatibility

**Files:**
- Create: `cogcoder/organization/runtime_part13.py` from accepted Part-XIII `runtime.py` byte-for-byte.
- Modify: `cogcoder/organization/runtime.py`
- Create: `tests/test_coding_agi_foundry_snapshot.py`

**Interfaces:**
- New `runtime.OrganizationRuntime` subclasses `runtime_part13.OrganizationRuntime`.
- Constructor adds optional `foundry: FoundryControlPlane | None`.
- `to_state()` adds `foundry` only.
- `from_state()` restores with `state.get('foundry', {})`; old state produces empty Foundry.

- [ ] Write RED snapshot tests covering zero-ephemeral state, rich round trip, destroyed scratch tombstone restore, corrupt digest/budget fail-closed and old snapshot without `foundry`.
- [ ] Run RED.
- [ ] Create byte-preserving Part-XIII runtime copy and thin Part-XIV façade.
- [ ] Run snapshot + Parts I–XIII regressions.
- [ ] Commit.

### Task 7: Adversarial suite, CI matrix, exact-head acceptance

**Files:**
- Create: `tests/test_coding_agi_foundry_adversarial.py`
- Create: `.github/workflows/coding-agi-ephemeral-foundry-part14.yml`

- [ ] Add adversarial cases for self-spawn, wrong-region spawn, tool escalation, quota overflow, mass-spawn overload, authority hijack, scratch leakage, stale child lease, failed-worker memory poisoning, sponsor-only verification, output after retirement, hidden reactivation, corrupt restore and fake matched-budget improvement.
- [ ] Add Python 3.11/3.13 workflow compiling `cogcoder/organization/*.py` and running `tests/test_coding_agi_foundry_*.py` plus all prior organization regressions.
- [ ] Freeze tests-only RED head and open draft PR; compile Parts I–XIII must succeed before expected missing-module RED.
- [ ] Build one exact GREEN candidate from accepted RED lineage; do not weaken tests.
- [ ] Verify GREEN 3.11/3.13 and independent Parts I–XIII workflows on the same exact SHA.
- [ ] Compare `main`→branch, update PR, mark ready, merge with `expected_head_sha`, verify merge receipt and close Issue #142.

## Self-review
- Spec coverage: every Issue #142 acceptance gate maps to Tasks 1–7.
- Placeholder scan: no TODO/TBD or unspecified authority shortcut remains.
- Type consistency: Part VIII is consumed unchanged; only permanent sponsor bridge artifacts become assurance subjects.
- Scope: Part XIV is a single temporary-execution lifecycle subsystem; model training and permanent-identity expansion remain outside scope.