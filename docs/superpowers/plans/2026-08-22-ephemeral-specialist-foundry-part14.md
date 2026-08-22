# Part XIV — Ephemeral Specialist Foundry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a governed optional Foundry that creates task-scoped temporary specialists without granting them permanent identity, authority, memory, or self-promotion privileges.

**Architecture:** Add focused Foundry modules above accepted Parts VIII, XII, and XIII. Temporary identities stay outside `AgentRegistry`; durable artifacts flow through `ArtifactStore`, engineering authorization through Part VIII, reusable skills through Part XII, and parent-task lineage through Part XIII. Part XIV runtime integration is a thin façade over the accepted Part-XIII runtime.

**Tech Stack:** Python 3.11/3.13, dataclasses/enums, existing Nolane organization primitives, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-22-ephemeral-specialist-foundry-part14-design.md`

## Global Constraints
- Permanent organization remains exactly 67 identities; ephemeral identities never enter `AgentRegistry`.
- Ephemeral workers never own authoritative artifacts and never write active permanent `MemoryFabric` directly.
- Only `nolane.central` or an authorized Regional Chief may approve spawning.
- First-generation Foundry ceilings: 12 active ephemeral workers organization-wide, 4 per team, 3 active teams per sponsor.
- Spawn budgets must have positive compute/tool/core/lifetime values.
- Engineering-authorizing handoff requires Part-VIII `VERIFIED`; `OVERRIDDEN` is not independent verification.
- Skill distillation produces only a permanent-owner `SkillScope.CANDIDATE`; Part XII owns promotion.
- Parent TaskGraph/Part-XIII lease lineage is authoritative; stale lease epoch blocks handoff/distillation.
- Destroyed scratch content must never reappear after snapshot restore.
- Zero-ephemeral runtime must preserve all Parts I–XIII behavior.

---

### Task 1: Profiles, spawn requests, and permanent-authority boundary

**Files:**
- Create: `cogcoder/organization/foundry_profiles.py`
- Create: `tests/test_coding_agi_foundry_profiles.py`
- Create: `tests/test_coding_agi_foundry_spawn.py`

**Interfaces:**
- Produces `FoundryTemplate`, `SpawnRequest`, `EphemeralIdentityManifest`, `FoundryProfileRegistry`.
- `FoundryProfileRegistry.request(...)` creates immutable REQUESTED spawn requests.
- `approve(request_id, actor_agent_id)` accepts only Central or authorized Regional Chief.
- `instantiate(request_id, current_token, parent_lease_id=None, parent_lease_epoch=None)` creates a content-addressed temporary manifest outside `AgentRegistry`.

- [ ] **Step 1: Write RED profile tests**
  Assert five canonical templates exist, manifests have unique ephemeral namespaces, and `runtime.registry.get(ephemeral_id)` raises `KeyError`.

- [ ] **Step 2: Write RED spawn-authority tests**
  Assert specialists cannot approve, wrong-region Chiefs cannot approve a regional parent task, and Central can approve explicit global diagnostic scope.

- [ ] **Step 3: Run RED tests**
  Run `pytest -q tests/test_coding_agi_foundry_profiles.py tests/test_coding_agi_foundry_spawn.py`.
  Expected: collection/import failure because `foundry_profiles` does not exist.

- [ ] **Step 4: Implement minimal immutable profile/spawn model**
  Validate sponsor IDs through permanent `AgentRegistry`, bind task scope through `TaskGraph`, and compute IDs with `canonical_digest`.

- [ ] **Step 5: Run Task-1 tests GREEN and commit**

### Task 2: Hard resource governance and concurrency

**Files:**
- Create: `cogcoder/organization/foundry_resources.py`
- Create: `tests/test_coding_agi_foundry_resources.py`

**Interfaces:**
- Produces `FoundryBudget`, `FoundryResourceKind`, `ResourceUsageReceipt`, `FoundryResourceGovernor`.
- `register_manifest(manifest, budget)` binds an immutable budget.
- `consume(ephemeral_id, resource_kind, units, actor_ephemeral_id)` fails closed on identity mismatch or exhaustion.
- `reserve_active(team_id, sponsor_agent_id, ephemeral_id)` enforces 12 organization / 4 team / 3 sponsor-team limits.

- [ ] **Step 1: Write RED budget tests**
  Cover positive-budget validation, exact counters, tool/core/compute exhaustion, actor mismatch, and no negative remaining budget.

- [ ] **Step 2: Write RED concurrency tests**
  Cover organization/team/sponsor limits and deterministic release on retirement.

- [ ] **Step 3: Run RED resource tests**
- [ ] **Step 4: Implement governor with content-addressed receipts**
- [ ] **Step 5: Run GREEN and commit**

### Task 3: Lifecycle and isolated scratch vault

**Files:**
- Create: `cogcoder/organization/foundry_lifecycle.py`
- Create: `cogcoder/organization/foundry_memory.py`
- Create: `tests/test_coding_agi_foundry_lifecycle.py`
- Create: `tests/test_coding_agi_foundry_memory.py`

**Interfaces:**
- Produces `FoundryStatus`, `FoundryLifecycleReceipt`, `FoundryLifecycleLedger`.
- Produces `ScratchDisposition`, `ScratchEntry`, `ScratchTombstone`, `EphemeralScratchVault`.
- Lifecycle only accepts declared forward transitions; all terminal states are non-reactivatable.
- Scratch writes require active matching ephemeral identity.
- `retire(..., DESTROY)` retains only digest/tombstone metadata.

- [ ] **Step 1: Write RED transition tests**
  Cover valid success path, rejection/exhaustion/quarantine/abort terminals, backward transition rejection, and hidden reactivation rejection.

- [ ] **Step 2: Write RED scratch tests**
  Prove cross-worker reads fail, permanent IDs cannot read scratch, destroy removes content, archive-quarantine never enters `MemoryFabric`, and restore does not resurrect destroyed content.

- [ ] **Step 3: Run RED lifecycle/memory tests**
- [ ] **Step 4: Implement ledgers and vault**
- [ ] **Step 5: Run GREEN and commit**

### Task 4: Output provenance, verification, assurance-aware handoff

**Files:**
- Create: `cogcoder/organization/foundry_evidence.py`
- Create: `tests/test_coding_agi_foundry_evidence.py`
- Create: `tests/test_coding_agi_foundry_authority.py`

**Interfaces:**
- Produces `FoundryOutputReceipt`, `FoundryVerificationReceipt`, `FoundryHandoffReceipt`.
- `emit_output()` writes durable content-addressed artifact with ephemeral producer provenance.
- `record_verification()` accepts only clean permanent external evidence; sponsor-only evidence is informational and cannot authorize engineering handoff.
- `authorize_handoff()` requires fresh parent lease plus Part-VIII `VERIFIED` decision for engineering-authorizing targets.

- [ ] **Step 1: Write RED provenance/verification tests**
  Cover artifact survival after retirement, permanent external verifier requirement, dirty evidence quarantine, and duplicate evidence id immutability.

- [ ] **Step 2: Write RED authority tests**
  Assert ephemeral IDs never gain `AuthorityGraph` ownership/write path; cross-region output remains proposal-only; Part-VIII `OVERRIDDEN` is rejected for independently authorized handoff.

- [ ] **Step 3: Run RED tests**
- [ ] **Step 4: Implement evidence/handoff receipts**
- [ ] **Step 5: Run GREEN and commit**

### Task 5: Foundry orchestration, stale lease containment, skill distillation, benefit measurement

**Files:**
- Create: `cogcoder/organization/foundry.py`
- Create: `tests/test_coding_agi_foundry_control_plane.py`
- Create: `tests/test_coding_agi_foundry_distillation.py`
- Create: `tests/test_coding_agi_foundry_benefit.py`

**Interfaces:**
- `FoundryControlPlane` composes registry/tasks/coordination/artifacts/assurance/evolution/individual_evolution plus Tasks 1–4 modules.
- `distill_skill(handoff_id, target_agent_id, name, body)` calls `SkillEvolutionEngine.propose()` only after success, clean verification, current lease lineage, and target ownership checks.
- `FoundryBenefitObservation` and `FoundryBenefitAssessment` compare same task/regime/budget only.

- [ ] **Step 1: Write RED stale-parent-lease tests**
  Instantiate on lease epoch N, revoke/reassign through Part XIII, then prove old ephemeral output cannot handoff or distill.

- [ ] **Step 2: Write RED skill tests**
  Assert result scope is `CANDIDATE`, permanent target is owner, quarantined/failed work cannot distill, and later promotion remains Part-XII governed.

- [ ] **Step 3: Write RED matched-budget tests**
  Same regime + higher score + no worse false accepts/regressions + within budget => improved; mismatched regime or budget => incomparable/not improved.

- [ ] **Step 4: Run RED tests**
- [ ] **Step 5: Implement `FoundryControlPlane` and benefit ledger**
- [ ] **Step 6: Run GREEN and commit**

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

- [ ] **Step 1: Write RED snapshot tests**
  Cover zero-ephemeral state, rich Foundry round trip, destroyed scratch tombstone restore, corrupt digest/budget fail-closed, and old snapshot without `foundry`.

- [ ] **Step 2: Run RED snapshot tests**
- [ ] **Step 3: Create Part-XIII runtime copy and thin Part-XIV façade**
- [ ] **Step 4: Run snapshot + Parts I–XIII regressions**
- [ ] **Step 5: Commit**

### Task 7: Adversarial suite, CI matrix, exact-head acceptance

**Files:**
- Create: `tests/test_coding_agi_foundry_adversarial.py`
- Create: `.github/workflows/coding-agi-ephemeral-foundry-part14.yml`

**Interfaces:**
- No new production API.

- [ ] **Step 1: Write adversarial RED/GREEN cases**
  Cover self-spawn, wrong-region spawn, tool escalation, quota overflow, mass-spawn overload, authority hijack, scratch leakage, stale child lease, failed-worker memory poisoning, self/sponsor-only verification, output after retirement, hidden reactivation, corrupt restore, and fake matched-budget improvement.

- [ ] **Step 2: Add Python 3.11/3.13 workflow**
  Compile `cogcoder/organization/*.py`; run `tests/test_coding_agi_foundry_*.py` plus all prior organization regression suites.

- [ ] **Step 3: Freeze tests-only RED head and open draft PR**
  Confirm compile Parts I–XIII succeeds and RED collection fails only because Part-XIV production modules are absent.

- [ ] **Step 4: Build one exact GREEN candidate from the accepted RED lineage**
  Do not weaken tests. Fix only root causes shown by logs.

- [ ] **Step 5: Verify GREEN matrix on Python 3.11 and 3.13**
  Both jobs must compile and pass Part XIV + prior organization regressions.

- [ ] **Step 6: Verify independent Parts I–XIII workflows on exact GREEN SHA**
  R1.9/R2.0i may be additional evidence; known unrelated legacy bundle failures are not relabeled as Part-XIV failures.

- [ ] **Step 7: Compare main→branch, update PR, mark ready, merge with `expected_head_sha`, verify merge receipt, and close Issue #142**

## Self-review
- Spec coverage: all Issue #142 acceptance gates map to Tasks 1–7.
- Placeholder scan: no TODO/TBD or unspecified implementation step remains.
- Type consistency: `FoundryControlPlane` consumes the exact accepted `AgentRegistry`, `TaskGraph`, `CoordinationControlPlane`, `ArtifactStore`, `AssuranceControlPlane`, `SkillEvolutionEngine`, and `IndividualEvolutionControlPlane` objects.
- Scope: Part XIV is one cohesive lifecycle subsystem; model training or permanent-identity expansion is outside scope.