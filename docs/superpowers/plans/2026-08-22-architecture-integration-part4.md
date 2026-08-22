# Architecture & Integration Part IV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build versioned Architecture and Integration authorities that prevent locally-correct changes from silently violating system boundaries or compatibility contracts.

**Architecture:** Add an immutable `ArchitectureGraph` plus ADR ledger, deterministic change-impact/compatibility engines, and a separate `IntegrationGraph`. Integrate them with existing Requirements/Planning/TaskGraph by reference only; do not duplicate authority stores.

**Tech Stack:** Python standard library, dataclasses/enums, existing `cogcoder.organization`, pytest, GitHub Actions Python 3.11/3.13.

**Spec:** `docs/superpowers/specs/2026-08-22-architecture-integration-part4-design.md`

## Global Constraints

- Architecture authority owner is `architecture.chief`.
- Integration authority owner is `integration.chief`.
- Worker concerns/proposals do not mutate authoritative graphs.
- Accepted mutations require explicit reason + evidence and are atomic.
- `DEPENDS_ON` architecture cycles fail closed with no partial mutation.
- `UNKNOWN` compatibility cannot authorize integration.
- Independent verification/security blocks are preserved; Central override remains labeled override.
- Architecture/Integration Chiefs must complete direct-work acceptance cases.
- Runtime restart must reproduce exact architecture/integration versions and digests.
- No AGI/frontier-equivalence claim is introduced.

---

### Task 1: Versioned ArchitectureGraph

**Files:**
- Create: `cogcoder/organization/architecture.py`
- Test: `tests/test_coding_agi_architecture_graph.py`

**Produces:** `ComponentKind`, `ComponentStatus`, `EdgeKind`, `InterfaceClass`, `InterfaceStability`, `ArchitectureComponent`, `InterfaceContract`, `ArchitectureEdge`, `ArchitectureRevision`, `ArchitectureGraph`, `ArchitectureControlPlane`.

- [ ] Write RED tests proving normal owner-only mutation, required reason/evidence, unknown endpoint/interface rejection, atomic `DEPENDS_ON` cycle rejection and canonical snapshot/restore.
- [ ] Add a worker `ARCHITECTURE_CONCERN` test proving `coding.backend.01` can emit a proposal but graph bytes remain unchanged.
- [ ] Run `python -m pytest -q tests/test_coding_agi_architecture_graph.py`; expected RED because `architecture.py` is absent.
- [ ] Implement copy-on-revision graph state with canonical digest and immutable revision history.
- [ ] Enforce `AuthorityGraph.require_write(actor, 'architecture-graph')` in `ArchitectureControlPlane.apply_revision`.
- [ ] Run focused tests; require PASS.

Representative atomicity contract:

```python
before = runtime.architecture.to_state()
with pytest.raises(ValueError, match='cycle'):
    runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief',
        reason='invalid dependency loop', evidence_refs=('EV-A-2',),
        upsert_edges=(ArchitectureEdge('edge-2', 'B', 'A', EdgeKind.DEPENDS_ON),),
    )
assert runtime.architecture.to_state() == before
```

---

### Task 2: Structured ADR ledger

**Files:**
- Create: `cogcoder/organization/adr.py`
- Test: `tests/test_coding_agi_architecture_adr.py`

**Produces:** `ADRStatus`, `ArchitectureDecision`, `ADRDecisionLedger`.

- [ ] RED tests require non-empty alternatives/decision/evidence and reject unknown architecture refs.
- [ ] Test immutable acceptance and supersession: accepted ADR remains in history; newer ADR points to the old id rather than deleting it.
- [ ] Test only `architecture.chief` can accept/reject/supersede; workers may create proposal events only.
- [ ] Implement content-addressed ADR digest and canonical counters.
- [ ] Require PASS plus ArchitectureGraph tests.

---

### Task 3: Change-impact and compatibility engines

**Files:**
- Create: `cogcoder/organization/change_impact.py`
- Create: `cogcoder/organization/compatibility.py`
- Test: `tests/test_coding_agi_architecture_impact.py`
- Test: `tests/test_coding_agi_integration_compatibility.py`

**Produces:**
- `ImpactSeverity`, `ImpactPacket`, `ChangeImpactEngine.compute(...)`;
- `CompatibilityClass`, `CompatibilityAssessment`, `CompatibilityEngine.assess(...)`.

- [ ] RED: change to public interface returns transitive dependents, requirement refs, plan refs and required verification classes deterministically.
- [ ] RED: same inputs produce same impact digest independent of insertion order.
- [ ] RED: unchanged signature is compatible; changed public signature without adapter/migration is breaking/unknown and cannot be labeled compatible.
- [ ] Implement graph traversal from changed components/interfaces through reverse dependency edges.
- [ ] Implement fail-closed compatibility rules using old/new signature digest, required direction and migration/adapter evidence.
- [ ] Require focused PASS.

---

### Task 4: IntegrationGraph and governed acceptance

**Files:**
- Create: `cogcoder/organization/integration.py`
- Test: `tests/test_coding_agi_integration_graph.py`
- Test: `tests/test_coding_agi_integration_conflicts.py`

**Produces:** `ChangeCandidateStatus`, `ChangeCandidate`, `IntegrationReceipt`, `IntegrationGraph`, `IntegrationControlPlane`.

- [ ] RED: candidate dependency cycles fail atomically.
- [ ] RED: deterministic ready/integration order.
- [ ] RED: candidate expecting stale ArchitectureGraph version is blocked.
- [ ] RED: `UNKNOWN`/`BREAKING` compatibility without explicit migration/verified exception blocks acceptance.
- [ ] RED: two individually valid but mutually conflicting candidates cannot both become integrated.
- [ ] RED: active Verification/Security block stays a block even if Central records a conflict decision; an explicit Central override is separately labeled.
- [ ] Implement owner-gated `integration.chief` decisions and immutable integration receipts.
- [ ] Require focused PASS.

---

### Task 5: Architecture reconciliation and direct-Chief acceptance

**Files:**
- Create: `cogcoder/organization/architecture_reconciliation.py`
- Test: `tests/test_coding_agi_architecture_reconciliation.py`
- Test: `tests/test_coding_agi_architecture_integration_direct_work.py`

**Produces:** `ArchitectureDriftClass`, `ArchitectureFinding`, `ArchitectureReconciler`.

- [ ] RED findings for undeclared dependency, missing component, interface signature drift and stale architecture ref.
- [ ] Prove reconciliation has no authority mutation side effect.
- [ ] Architecture Chief leases and completes a difficult boundary/ADR task using ordinary Part-I `chief_direct_work` + artifact provenance.
- [ ] Integration Chief leases and completes a difficult multi-candidate compatibility adjudication task the same way.
- [ ] Require focused PASS.

---

### Task 6: Runtime/context/snapshot + exact hosted acceptance

**Files:**
- Modify: `cogcoder/organization/runtime.py`
- Modify: `cogcoder/organization/context.py`
- Test: `tests/test_coding_agi_architecture_integration_snapshot.py`
- Test: `tests/test_coding_agi_architecture_integration_context.py`
- Create: `.github/workflows/coding-agi-architecture-integration-part4.yml`

**Runtime interfaces:**
- `runtime.architecture: ArchitectureControlPlane`
- `runtime.integration: IntegrationControlPlane`
- `runtime.adr: ADRDecisionLedger`
- context authoritative artifacts include `architecture-graph` and `integration-state` versions.

- [ ] RED snapshot: architecture revision, ADR, compatibility assessment and integration candidate survive `OrganizationSnapshot` round-trip exactly.
- [ ] RED context: an agent checkpointed before architecture/integration revisions wakes with relevant authoritative delta and current versions, not full old history.
- [ ] Integrate stores after registry/authority/requirements/planning/tasks restore; keep Part I–III APIs backward compatible.
- [ ] Add Python 3.11/3.13 workflow running all `tests/test_coding_agi_architecture_*.py`, `tests/test_coding_agi_integration_*.py`, plus Part I–III organization regressions.
- [ ] Open draft PR against accepted `main`; capture RED before production implementation.
- [ ] Require exact-head GREEN on 3.11 and 3.13 plus Foundation/Central/Requirements-Planning regression lanes before merge.

## Plan self-review

- Spec coverage: graph/revisions, interfaces, ADRs, concern flow, blast radius, compatibility, integration DAG/change control, independent blocks, reconciliation, direct Chief work, context and restart all map to tasks.
- Placeholder scan: no TBD/TODO or unspecified implementation placeholder remains.
- Type consistency: architecture/integration/ADR names are stable across all tasks.
- Scope: repository symbol extraction belongs to Coding/Research Parts; Security verification execution belongs to Part VIII. Part IV consumes evidence references rather than duplicating those systems.