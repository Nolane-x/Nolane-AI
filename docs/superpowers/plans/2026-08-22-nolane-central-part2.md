# Nolane Central Part II Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a replayable Central control plane and direct-worker kernel on top of the Part-I organizational substrate without granting Central silent ownership of specialist-private cores.

**Architecture:** Add focused Central capability, resource, conflict, access-lease and direct-work components, then integrate them into `OrganizationRuntime` serialization. Reuse Part-I registry/events/authority/memory/artifacts/self-model/evolution/verification as the only durable authority instead of creating parallel stores.

**Tech Stack:** Python standard library, dataclasses, existing `cogcoder.organization` package, pytest, GitHub Actions Python 3.11/3.13.

**Spec:** `docs/superpowers/specs/2026-08-22-nolane-central-part2-design.md`

## Global Constraints

- First-generation Central physical parameter count remains `<100_000_000`.
- No AGI/frontier-equivalence capability claim is introduced.
- State-changing Central actions are typed, evidence-linked and replayable.
- Region-private external cores remain unavailable to Central without an explicit bounded lease.
- Verification/Security blocks are never converted into successful verification by a conflict decision.
- Snapshot/restore must preserve canonical counters, leases, allocations, conflicts and direct-work receipts.
- No new third-party Python dependency.

---

### Task 1: Central capability map and world-state digest

**Files:**
- Create: `cogcoder/organization/central_state.py`
- Modify: `cogcoder/organization/types.py`
- Test: `tests/test_coding_agi_central_state.py`

**Interfaces:**
- Consumes: `AgentRegistry`, `TaskGraph`, `AuthorityGraph`, `EventLedger`, `VerificationAuthority`.
- Produces: `CentralCapabilityObservation`, `CentralCapabilityMap`, `CentralWorldState`, `build_world_state(...)`.

- [ ] **Step 1: Write failing tests**

```python
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.central_state import CentralCapabilityMap, build_world_state


def test_capability_observation_requires_evidence_and_roundtrips():
    runtime = OrganizationRuntime.first_generation()
    mapping = CentralCapabilityMap(runtime.registry)
    row = mapping.observe(
        agent_id='coding.backend.01',
        readiness=73,
        health=91,
        evidence_refs=('evidence-cap-1',),
    )
    assert row.readiness == 73
    assert CentralCapabilityMap.from_state(runtime.registry, mapping.to_state()).to_state() == mapping.to_state()


def test_world_state_digest_is_deterministic():
    runtime = OrganizationRuntime.first_generation()
    left = build_world_state(runtime)
    right = build_world_state(runtime)
    assert left.digest == right.digest
```

- [ ] **Step 2: Run RED gate**

Run: `python -m pytest -q tests/test_coding_agi_central_state.py`
Expected: FAIL because `cogcoder.organization.central_state` does not exist.

- [ ] **Step 3: Implement minimal immutable observation/state types**

Implement bounded integer validation (`0..100`), required evidence, monotonic observation ids, canonical serialization and a digest built from registry/task/authority/event/capability/verification summaries.

- [ ] **Step 4: Run task tests**

Run: `python -m pytest -q tests/test_coding_agi_central_state.py`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: add Central capability and world-state model`.

---

### Task 2: Bounded resource arbitration

**Files:**
- Create: `cogcoder/organization/central_resources.py`
- Test: `tests/test_coding_agi_central_resources.py`

**Interfaces:**
- Produces: `ResourceAllocationReceipt`, `CentralResourceArbiter` with `allocate`, `release`, `available`, `leased_to`, `to_state`, `from_state`.

- [ ] **Step 1: Write failing accounting tests**

```python
import pytest
from cogcoder.organization.central_resources import CentralResourceArbiter


def test_resource_allocation_is_exact_and_fail_closed():
    arbiter = CentralResourceArbiter({'compute': 100, 'agent_slots': 8})
    receipt = arbiter.allocate(
        beneficiary='coding.backend.01', resource='compute', amount=30,
        reason='compile repair candidate', evidence_refs=('evidence-r1',),
    )
    assert receipt.before_available == 100
    assert receipt.after_available == 70
    with pytest.raises(ValueError):
        arbiter.allocate(
            beneficiary='coding.backend.01', resource='compute', amount=71,
            reason='over budget', evidence_refs=('evidence-r2',),
        )
    assert arbiter.available('compute') == 70


def test_resource_restore_preserves_leases():
    arbiter = CentralResourceArbiter({'compute': 100})
    arbiter.allocate(
        beneficiary='debug.chief', resource='compute', amount=40,
        reason='trace investigation', evidence_refs=('evidence-r3',),
    )
    restored = CentralResourceArbiter.from_state(arbiter.to_state())
    assert restored.to_state() == arbiter.to_state()
```

- [ ] **Step 2: Run RED**, expecting missing module failure.
- [ ] **Step 3: Implement exact integer resource accounting with no partial mutation on failure.**
- [ ] **Step 4: Run tests and require PASS.**
- [ ] **Step 5: Commit** as `feat: add Central resource arbitration`.

---

### Task 3: Cross-region conflict packets

**Files:**
- Create: `cogcoder/organization/central_conflicts.py`
- Test: `tests/test_coding_agi_central_conflicts.py`

**Interfaces:**
- Produces: `ConflictStatus`, `ConflictClaim`, `CentralConflictPacket`, `CentralConflictRegistry`.
- Consumes: `AuthorityGraph`, `EventLedger` when integrated later.

- [ ] **Step 1: Write failing conflict tests**

```python
from cogcoder.organization.central_conflicts import CentralConflictRegistry, ConflictStatus


def test_conflict_requires_competing_claims_and_resolution_evidence():
    registry = CentralConflictRegistry()
    packet = registry.open(
        submitted_by=('coding.chief', 'architecture.chief'),
        regions=('core-coding', 'architecture-system'),
        object_refs=('architecture-graph',),
        claims=(
            ('coding.chief', 'interface can remain mutable', ('ev-c1',)),
            ('architecture.chief', 'interface must freeze', ('ev-c2',)),
        ),
        severity=80,
    )
    resolved = registry.resolve(
        packet.conflict_id,
        resolver_agent_id='nolane.central',
        decision='freeze interface',
        rationale='cross-region compatibility evidence',
        evidence_refs=('ev-resolution',),
    )
    assert resolved.status is ConflictStatus.RESOLVED
```

Also test rejection of a one-claim packet, empty resolution evidence, invalid severity and non-canonical restore counters.

- [ ] **Step 2: Run RED.**
- [ ] **Step 3: Implement immutable claims/packets plus canonical state.**
- [ ] **Step 4: Run task tests and require PASS.**
- [ ] **Step 5: Commit** as `feat: add Central conflict registry`.

---

### Task 4: Governed external-core leases

**Files:**
- Create: `cogcoder/organization/central_access.py`
- Test: `tests/test_coding_agi_central_access.py`

**Interfaces:**
- Produces: `CoreLease`, `CentralCoreAccessPolicy` with `can_invoke`, `grant_lease`, `consume`, `revoke`, `to_state`, `from_state`.
- Consumes: `AgentRegistry`, `ExternalCoreRegistry`.

- [ ] **Step 1: Write failing ownership tests**

```python
import pytest
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.central_access import CentralCoreAccessPolicy


def test_central_cannot_silently_take_private_region_core():
    runtime = OrganizationRuntime.first_generation()
    policy = CentralCoreAccessPolicy(runtime.registry, runtime.external_cores)
    assert policy.can_invoke('global-project-graph', token=1)
    assert not policy.can_invoke('runtime-tracer', token=1)

    lease = policy.grant_lease(
        core_id='runtime-tracer', owner='debugging-failure', call_budget=2,
        expires_at_token=10, reason='cross-region incident', evidence_refs=('ev-core-1',),
    )
    assert policy.consume(lease.lease_id, token=2).remaining_calls == 1
    assert policy.consume(lease.lease_id, token=3).remaining_calls == 0
    with pytest.raises(PermissionError):
        policy.consume(lease.lease_id, token=4)
```

- [ ] **Step 2: Run RED.**
- [ ] **Step 3: Implement owner-aware access and bounded leases.**
- [ ] **Step 4: Run task tests and require PASS.**
- [ ] **Step 5: Commit** as `feat: govern Central external-core access`.

---

### Task 5: Central control plane and direct-work receipts

**Files:**
- Create: `cogcoder/organization/central.py`
- Modify: `cogcoder/organization/types.py`
- Modify: `cogcoder/organization/runtime.py`
- Test: `tests/test_coding_agi_central_control.py`

**Interfaces:**
- Produces: `CentralDirectWorkReceipt`, `CentralControlPlane`.
- `CentralControlPlane` owns references to capability map, arbiter, conflicts and core-access policy but not duplicated Part-I stores.

- [ ] **Step 1: Write failing intervention/direct-work tests**

```python
import pytest
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind


def test_direct_correction_is_same_authoritative_event_for_target_and_chief():
    runtime = OrganizationRuntime.first_generation()
    event = runtime.central.correct(
        target_agent_id='coding.backend.01',
        directive='do not mutate architecture authority',
        evidence_refs=('ev-central-1',),
    )
    target_ids = {x.event_id for x in runtime.ledger.deliverable_for('coding.backend.01')}
    chief_ids = {x.event_id for x in runtime.ledger.deliverable_for('coding.chief')}
    assert event.event_id in target_ids
    assert event.event_id in chief_ids


def test_central_direct_work_requires_artifact_and_evidence():
    runtime = OrganizationRuntime.first_generation()
    task = runtime.tasks.create(
        title='bounded architecture audit', owner_agent_id='nolane.central',
        owner_region='global-command', plan_node='P-central', requirements=('R1',),
        acceptance_criteria=('A1',), created_by='nolane.central',
    )
    artifact = runtime.artifacts.put(
        kind='analysis', producer_agent_id='nolane.central', content='bounded result',
        evidence_refs=('ev-work-1',),
    )
    receipt = runtime.central.complete_direct_work(
        task_id=task.task_id,
        artifact_ids=(artifact.artifact_id,),
        evidence_refs=('ev-work-1',),
    )
    assert receipt.task_id == task.task_id
```

Also test `pause`, `abort`, `request_evidence`, missing evidence rejection and preservation of independent authority blocks.

- [ ] **Step 2: Run RED.**
- [ ] **Step 3: Add Central event kinds and implement `CentralControlPlane`.**
- [ ] **Step 4: Integrate `runtime.central` in `OrganizationRuntime.first_generation()`.**
- [ ] **Step 5: Run central-control tests and the entire Part-I contract suite.**
- [ ] **Step 6: Commit** as `feat: integrate Nolane Central control plane`.

---

### Task 6: Snapshot/restart and full Part-II acceptance suite

**Files:**
- Modify: `cogcoder/organization/runtime.py`
- Modify: `cogcoder/organization/snapshot.py` only if runtime serialization contract requires it
- Create: `tests/test_coding_agi_central_snapshot.py`
- Create: `tests/test_coding_agi_central_acceptance.py`
- Create: `.github/workflows/coding-agi-central-part2.yml`

**Interfaces:**
- `OrganizationRuntime.to_state()` includes key `central`.
- `OrganizationRuntime.from_state()` restores `CentralControlPlane` against the reconstructed Part-I stores.

- [ ] **Step 1: Write restart acceptance test**

```python
from cogcoder.organization.runtime import OrganizationRuntime


def test_central_world_state_is_exact_after_restore():
    runtime = OrganizationRuntime.first_generation()
    runtime.central.resources.allocate(
        beneficiary='coding.chief', resource='compute', amount=10,
        reason='bounded direct coding', evidence_refs=('ev-s1',),
    )
    before = runtime.central.world_state().digest
    restored = OrganizationRuntime.from_state(runtime.to_state())
    assert restored.central.world_state().digest == before
    assert restored.central.to_state() == runtime.central.to_state()
```

Acceptance suite additionally checks:
- exactly one Central identity and `<100M` physical parameters;
- private-core lease policy;
- direct target + Chief event visibility;
- resource exactness;
- conflict resolution + independent block preservation;
- direct-work receipt provenance;
- self-model/skill/neural promotion remains governed by Part-I authorities.

- [ ] **Step 2: Run RED.**
- [ ] **Step 3: Implement serialization/rebinding.**
- [ ] **Step 4: Add Python 3.11/3.13 workflow executing `tests/test_coding_agi_central_*.py` plus all `tests/test_coding_agi_foundation_*.py`.**
- [ ] **Step 5: Run local/focused verification when an execution environment is available.**
- [ ] **Step 6: Open a stacked PR against `feat/coding-agi-foundation-part1-gpt56sol`, require hosted GREEN, then retarget to `main` only after Part I merges.**
- [ ] **Step 7: Commit** as `test: lock Nolane Central Part II acceptance`.

## Plan self-review

- Spec coverage: capability map, world-state reconstruction, intervention, resources, conflicts, direct work, core ownership, evolution hooks and restart all have explicit tasks.
- Placeholder scan: no TBD/TODO/future implementation placeholders are used.
- Type consistency: component names and runtime `central` integration are consistent across tasks.
- Scope: Part II remains Central-only; Requirements/Planning work stays in Part III.
