# D. Goal / Design — Federated Coherence + Live Authority Runtime

## Status

This document defines the upgraded architecture for Nolane AI's **D. Goal / Design** domain:

- Requirements
- Planning
- Architecture
- Integration
- Context

D is intentionally **federated**. The five specialist authorities remain independently evolvable. `GoalDesignCoherencePlane` is the decision/coherence authority and `GoalDesignRuntime` is the operational membrane that observes the real five control planes, propagates change impact, binds decisions to exact state, and fails closed when authority drifts.

Nolane World 0.12.0 was used as architectural research, not as a runtime dependency.

---

## Why the previous shape was insufficient

The pre-upgrade D modules already had useful local control planes:

- requirement graph + revisions,
- planning DAG + risks,
- architecture components/interfaces/dependency graph,
- integration candidate graph + compatibility gates,
- context capsules + authoritative-artifact versions.

The missing capability was a system-level answer to two harder questions:

> Is this design decision still valid against the exact Requirements + Planning + Architecture + Integration + Context state that justified it?

and

> If one authority changes, which downstream plans, components, interfaces, integration candidates, contexts and prior decisions have become stale?

Local validity is not enough. Five individually valid planes can still form a globally stale design.

---

## Core invariants

1. **No authority collapse.** Requirements, Planning, Architecture, Integration and Context retain separate ownership and state.
2. **Observe, do not impersonate.** `GoalDesignRuntime` reads the five specialist authorities; it does not become their writer.
3. **Exact state binding.** Every admitted design decision is bound to a five-plane `GoalDesignVersionVector` and content-addressed snapshot.
4. **Fail closed on drift.** Changing any plane invalidates the old snapshot for future authority actions.
5. **Thought is not authority.** Generic observations/proposals cannot self-promote to authority.
6. **Invalidation is authority.** Withdrawing a previously admitted decision uses a typed `INVALIDATION` authority event, not a generic evidence event.
7. **Vector goals remain vector goals.** Pareto dominance is evaluated per declared objective; scalar helper scores cannot override the Pareto authority set.
8. **Irreversibility changes burden of proof.** Costly/irreversible decisions require alternatives, counterfactual/adversarial scenarios and stronger uncertainty closure.
9. **Unknowns are first-class.** Uncertainty is prioritized by uncertainty × impact × decision sensitivity × observability penalty.
10. **Evidence is inherited into receipts.** Goal, option, proof and uncertainty evidence is folded into deterministic decision receipts.
11. **Traceability is cross-plane.** Active Requirements must reach Planning; Plans must reach Architecture; Integration refs must resolve to live Architecture; Context must bind exact authoritative artifact versions.
12. **Historical identity is not live authority.** Removed/superseded architecture components, superseded plans and rejected/superseded integration candidates are not accepted merely because their IDs remain in historical graphs.
13. **Authority survives restart.** Decision lifecycle and causal ledger state have canonical serialization and validation.
14. **Transitive impact is directional.** A changed dependency invalidates its consumers and downstream integration chain; dependency direction is not reversed accidentally.

---

## Architecture

```text
                         GoalSpec / objective vector
                                   │
                         uncertainty frontier
                                   │
          ┌────────────────────────┴────────────────────────┐
          │                                                 │
   scenarios / alternatives                         proof obligations
          │                                                 │
          └────────────────────────┬────────────────────────┘
                                   │
                         GoalDesignCoherencePlane
                                   │
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
       Pareto gate          robust evaluation       admission gate
            │                      │                      │
            └──────────────────────┼──────────────────────┘
                                   │
                    GoalDesignRuntime (observer/membrane)
                                   │
       ┌──────────────┬────────────┬──────────────┬─────────────┬─────────┐
       │ Requirements │  Planning  │ Architecture │ Integration │ Context │
       └──────────────┴────────────┴──────────────┴─────────────┴─────────┘
                                   │
                         live state bundle
                                   │
                    five-plane version vector
                                   │
                    content-addressed snapshot
                                   │
                        DecisionReceipt
                                   │
                     DecisionAuthorityIndex
                                   │
               ACTIVE / STALE / SUPERSEDED / REVOKED
                                   │
                    GoalDesignLedger authority DAG
```

---

## 1. Requirements authority

### Canonical source

The existing `RequirementGraph` remains authoritative.

### Output observed by D

- graph revision/version,
- graph digest,
- active requirement IDs,
- acceptance evidence expectations.

### Semantics

- Only `ACTIVE` requirements enter the active requirement set.
- Requirement history stays in the requirements graph; D does not erase or rewrite it.
- A changed requirement can propagate into every plan node that traces it and every architecture component implementing those plans.

---

## 2. Planning authority

### Canonical source

The existing `MasterPlanGraph` remains authoritative.

### Output observed by D

- plan graph revision/version,
- graph digest,
- requirement coverage,
- risk refs,
- plan nodes used as propagation anchors.

### Semantics

- Superseded plan nodes are not treated as current planning coverage.
- Plan DAG structure stays locally owned by Planning.
- D uses plan references to bridge requirement impact into architecture impact.

---

## 3. Architecture authority

### Canonical source

The existing `ArchitectureGraph` remains authoritative.

### Output observed by D

- graph version + digest,
- live component IDs,
- live interface IDs,
- dependency edges.

### Semantics

- `REMOVED` and `SUPERSEDED` components remain historical graph facts but are not live authority.
- Interfaces whose producer is no longer a live component are not emitted as live architecture interfaces.
- A `DEPENDS_ON` edge is interpreted directionally: `source` depends on `target`; a target change propagates to the source/consumer.
- Interface consumer scope extends impact into declared consumers.

---

## 4. Integration authority

### Canonical source

The existing `IntegrationGraph` remains authoritative.

### Output observed by D

- graph version + digest,
- non-rejected/non-superseded candidate component refs,
- candidate requirement/plan/component/interface/dependency refs.

### Exact Goal/Design integration guard

Before a candidate is accepted as coherent with D, `guard_integration()` verifies:

1. the supplied Goal/Design snapshot still equals live five-plane state;
2. candidate expected architecture version equals the current architecture version;
3. requirement refs exist and are active;
4. plan refs exist and are not superseded;
5. component refs exist and are not removed/superseded;
6. interface refs exist and their producers remain live;
7. candidate itself is not rejected/superseded.

A successful check emits a content-addressed `IntegrationGuardReceipt` bound to the exact Goal/Design snapshot.

Compatibility evidence from Integration remains necessary; the Goal/Design guard adds cross-plane freshness and authority coherence rather than replacing Integration's own compatibility gate.

---

## 5. Context authority

Context is treated as a **compiled decision substrate**, not an unbounded history bag.

### Context state token

The runtime derives a stable context authority token from policy-level state:

- explicit context policy version,
- context component version when the implementation module exposes one,
- memory/event bounds.

Transient counts or last-event fields do not change the authority token by themselves.

### Exact context binding

`bind_context()` requires the capsule's authoritative artifact versions to exactly match live:

- `master-plan`,
- `requirements`,
- `architecture-graph`,
- `integration-state`.

It also requires the Goal/Design snapshot itself to still be current.

A successful bind emits a content-addressed `ContextBindingReceipt`.

---

## Live five-plane state bundle

`GoalDesignRuntime.observe()` adapts real Nolane control-plane state into:

- `RequirementsState`
- `PlanningState`
- `ArchitectureState`
- `IntegrationState`
- `ContextState`

These form `GoalDesignStateBundle`, whose `version_vector` is the exact state identity used by D.

This removes the previous operational gap where the coherence layer existed but callers still had to manually construct five-plane state.

---

## Version vector and snapshots

A `GoalDesignVersionVector` contains one token for each authority:

```text
requirements = revision@digest
planning     = revision@digest
architecture = revision@digest
integration  = revision@digest
context      = policy@digest
```

`freeze()` creates a deterministic SHA-256 snapshot over the vector and records a typed snapshot authority event.

If any token later differs, `verify_snapshot()` emits a blocking stale-plane issue.

---

## Change-impact propagation

`GoalDesignRuntime.analyze_change()` computes a deterministic transitive closure over real D graphs.

Canonical propagation path:

```text
Changed Requirement
        │
        ▼
Plan nodes tracing requirement
        │
        ▼
Architecture components tracing requirement/plan
        │
        ├──────────────► interfaces produced by affected component
        │                               │
        │                               ▼
        │                       declared interface consumers
        │                               │
        ▼                               ▼
components that DEPEND_ON affected components
        │
        ▼
Integration candidates touching affected requirement / plan /
component / interface
        │
        ▼
Integration candidates depending on affected candidates
        │
        ▼
Compiled Context invalidated for revalidation
```

The result is a content-addressed `GoalDesignImpactReport` containing:

- changed refs,
- affected plan refs,
- affected component refs,
- affected interface refs,
- affected integration candidate refs,
- context invalidation flag,
- causal reasons,
- deterministic digest.

This is the mechanism that lets independently evolving specialist AIs invalidate only the part of D that actually depends on their changes.

---

## Decision lifecycle

An admitted decision is indexed as an immutable receipt plus mutable lifecycle authority:

```text
ACTIVE
  ├── authority drift / impacted dependency ──► STALE
  ├── explicit replacement                  ──► SUPERSEDED
  └── explicit withdrawal                   ──► REVOKED
```

The receipt itself is immutable. Lifecycle state is held in `DecisionAuthorityIndex`.

### Dependency-aware invalidation

Each admitted design option records its requirement/component dependencies. When an impact report overlaps those dependencies, `invalidate_impacted_decisions()` marks the decision `STALE` and emits a typed authority invalidation event.

### Whole-snapshot revalidation

Even if no explicit change-set was supplied, `revalidate_decisions()` reconstructs the original five-plane snapshot from every active decision receipt and compares it with live state. Authority drift therefore cannot remain active merely because an upstream agent forgot to emit an explicit change-set.

---

## Authority persistence and restart safety

`DecisionAuthorityIndex` has a canonical schema:

- receipt payload,
- dependency refs,
- snapshot digest,
- lifecycle,
- invalidation reasons,
- decision authority event ID,
- supersession target.

`to_state()` and `from_state()` preserve this state across restart. Restore validates:

- schema version,
- duplicate receipt identity,
- snapshot digest agreement,
- valid lifecycle values,
- canonical dependency/reason normalization,
- supersession references.

The index itself exposes a deterministic digest.

`GoalDesignLedger` is also serializable. Restore validates:

- canonical monotonic event sequence,
- duplicate event identity,
- causal parents appearing before children,
- content-addressed event identity digest.

This prevents persistence from silently converting corrupted authority history into valid runtime state.

---

## Thought / evidence / authority separation

The ledger has three semantic levels:

- `THOUGHT` — speculative proposals/observations;
- `EVIDENCE` — supporting observations and verification material;
- `AUTHORITY` — state/decision transitions that govern what downstream code may trust.

Generic callers cannot call `append(... AUTHORITY ...)`.

Typed authority methods mint:

- snapshot authority,
- decision authority,
- invalidation authority.

An invalidation is intentionally authoritative because it withdraws permission to treat a prior decision as current closure.

---

## Decision theory adapted from Nolane World 0.12.0

Nolane World is not imported as a runtime library. The following mechanisms were translated into D-specific semantics:

- uncertainty frontier,
- robust planning under scenario uncertainty,
- Pareto frontier preservation,
- counterfactual/adversarial branching,
- proof obligations,
- lower-tail risk,
- maximum regret,
- reversibility and option value,
- invariant checking,
- truth-maintenance style invalidation,
- content-addressed evidence/authority lineage,
- separation of speculative cognition from closure authority.

The point is not to copy World APIs. The point is to reuse its deeper reasoning machinery while preserving Nolane AI's own boundaries.

---

## Evaluation semantics

For each design option and scenario, D computes:

- expected utility,
- worst-case utility,
- lower-tail utility over the worst 25% probability mass,
- maximum scenario regret,
- optionality from reversibility,
- bounded robust helper score.

The helper score is diagnostic/ranking support only. If objectives are declared, the selected option must still belong to the Pareto frontier.

This avoids collapsing multi-objective design into one scalar that can optimize the wrong proxy.

---

## Admission semantics

A design decision is rejected when any blocker exists, including:

- stale/corrupted five-plane snapshot,
- unresolved blocking proof obligation,
- cross-plane traceability gap,
- costly/irreversible decision with no explicit alternative,
- costly/irreversible decision with no counterfactual/adversarial scenario,
- costly-reversible decision with no rollback reference,
- irreversible decision with unresolved high-risk uncertainty,
- Pareto-dominated selected option.

Successful admission emits deterministic `DecisionReceipt` authority and records it as a child of the exact snapshot event that justified it.

---

## Concurrency with A/B/C/... specialist agents

This architecture is deliberately compatible with concurrent specialist development.

D does not seize authority from A, B, C or other domains. It also does not require those agents to share internal implementation details. Their effects enter D when the D authority surfaces they influence change revision/digest or when explicit affected refs are supplied.

Consequences:

- specialist agents can evolve independently;
- D can detect a stale decision after their change;
- old snapshots are never silently reinterpreted as current state;
- impact propagation narrows revalidation to downstream dependencies when possible;
- whole-snapshot revalidation remains the safety net when explicit impact metadata is absent.

This is the intended coordination membrane between Goal/Design and the rest of Nolane AI.

---

## Files

### Core

- `nolane/external_core/goal_design.py` — goals, objectives, uncertainty, scenarios, Pareto/robust evaluation, snapshots, coherence, admission, receipts.
- `nolane/external_core/goal_design_contracts.py` — typed five-authority state bundle.
- `nolane/external_core/goal_design_ledger.py` — causal authority ledger, typed invalidation and persistence.
- `nolane/external_core/goal_design_runtime.py` — live adapters, impact propagation, decision lifecycle, integration/context guards and authority persistence.
- `cogcoder/organization/goal_design.py` — compatibility export surface.

### Tests

- `tests/test_goal_design_coherence_plane.py`
- `tests/test_goal_design_contracts.py`
- `tests/test_goal_design_ledger.py`
- `tests/test_goal_design_runtime.py`
- `tests/test_goal_design_authority_persistence.py`

### CI

- `.github/workflows/goal-design-coherence-plane.yml`

The dedicated workflow discovers `tests/test_goal_design*.py` and verifies D on Python 3.11 and 3.12.

---

## Stable evolution boundary

Future specialist upgrades may make each local D plane substantially more sophisticated without breaking this layer. The stable cross-plane integration surface is:

```text
specialist authority state
        ↓
revision + digest + typed refs
        ↓
GoalDesignStateBundle
        ↓
GoalDesignVersionVector
        ↓
GoalDesignSnapshot
        ↓
DecisionReceipt / IntegrationGuardReceipt / ContextBindingReceipt
        ↓
causal authority ledger + lifecycle index
```

Local implementation details should not leak across authority boundaries. D should get stronger by improving contracts, evidence, impact precision and validation—not by centralizing every subsystem into one mutable controller.
