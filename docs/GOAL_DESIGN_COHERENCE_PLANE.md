# D. Goal / Design — Federated Coherence Plane

## Status

This document defines the upgraded architecture for Nolane AI's **D. Goal / Design** domain:

- Requirements
- Planning
- Architecture
- Integration
- Context

The implementation is intentionally **federated**. The five existing specialist authorities remain independently evolvable; `GoalDesignCoherencePlane` is a cross-plane authority gate, not a replacement for them.

## Why the previous shape was insufficient

The existing D modules already provide useful local control planes: requirements graphs and revisions, plan DAGs, architecture/interface graphs, integration compatibility gates, and context capsules. The missing capability was a system-level answer to a harder question:

> Is this design decision still valid against the exact Requirements + Planning + Architecture + Integration + Context state that justified it?

Without this layer, each local plane can be individually valid while the combined design has drifted.

## Core invariants

1. **No authority collapse.** Requirements, Planning, Architecture, Integration and Context keep separate state and ownership.
2. **Exact state binding.** Every admitted design decision is bound to a five-plane `GoalDesignVersionVector` and a content-addressed snapshot digest.
3. **Fail closed on drift.** A changed plane invalidates the old snapshot for new authority decisions.
4. **Thought is not authority.** Proposals and observations cannot self-promote into authoritative decisions. Typed authority methods mint snapshot/decision ledger events.
5. **Vector goals remain vector goals.** Pareto dominance is evaluated per declared objective and direction; helper scalar scores never override the Pareto authority set.
6. **Irreversibility changes the burden of proof.** Costly/irreversible choices require alternatives and counterfactual/adversarial scenarios. Costly-reversible changes require rollback references.
7. **Unknowns are first-class.** The uncertainty frontier prioritizes uncertainty by uncertainty × impact × decision sensitivity × observability penalty. High-risk unresolved uncertainty blocks irreversible authority.
8. **Evidence is inherited into receipts.** Goal, option, proof and uncertainty evidence references are folded into content-addressed decision receipts.
9. **Traceability is cross-plane.** Active requirements must reach Planning; planned components must reach Architecture; Integration references must exist in Architecture; Context staleness is surfaced.
10. **Context is design-state-bound.** Integration and Context may explicitly bind the snapshot they were compiled/evaluated against; stale bindings are blockers.

## Architecture

```text
                     GoalSpec / objective vector
                               │
                     uncertainty frontier
                               │
       ┌───────────────────────┴───────────────────────┐
       │                                               │
 design scenarios / alternatives               proof obligations
       │                                               │
       └───────────────────────┬───────────────────────┘
                               │
                     GoalDesignCoherencePlane
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
       Pareto gate      robust evaluation    admission gate
            │                  │                  │
            └──────────────────┼──────────────────┘
                               │
              five-plane immutable state bundle
                               │
  ┌────────────┬───────────┬──────────────┬─────────────┬─────────┐
  │Requirements│ Planning  │ Architecture │ Integration │ Context │
  └────────────┴───────────┴──────────────┴─────────────┴─────────┘
                               │
                     version-vector snapshot
                               │
                     DecisionReceipt (SHA-256)
                               │
                    append-only causal ledger
```

## Five specialist contracts

### Requirements

Authoritative output to D:
- revision + digest
- active requirement IDs
- acceptance/proof references

Expected semantics:
- preserve assumptions and non-goals explicitly
- distinguish desired behavior from acceptance proof
- changes create a new authority revision rather than mutating past design evidence

### Planning

Authoritative output to D:
- revision + digest
- requirement references covered by the plan
- planned component IDs
- risk references

Expected semantics:
- plans remain DAG/hierarchical artifacts
- design alternatives are not prematurely collapsed
- robust evaluation should include expected, worst-case, lower-tail, regret and optionality signals

### Architecture

Authoritative output to D:
- revision + digest
- component IDs
- interface IDs
- invariant IDs

Expected semantics:
- Architecture is an authority graph, not a prose diagram
- interfaces and invariants are design obligations
- a planned component that is absent from the Architecture authority graph is a blocker

### Integration

Authoritative output to D:
- revision + digest
- architecture component references
- bound Goal/Design snapshot digest
- rollback references

Expected semantics:
- an integration candidate cannot rely on a stale architecture/design snapshot
- compatibility evidence is necessary but not sufficient when the cross-plane version vector has drifted

### Context

Authoritative output to D:
- revision + digest
- referenced architecture components
- bound Goal/Design snapshot digest
- stale-context warnings

Expected semantics:
- context is a compiled decision substrate, not an unbounded bag of history
- stale warnings are retained rather than silently dropped
- verifier/reviewer context can be independently compiled from the same authority snapshot

## Decision theory imported from Nolane World

Nolane World 0.12.0 was used as architectural research, not as a runtime dependency. The following mechanisms were adapted into D-specific semantics:

- uncertainty frontier
- robust planning under scenario uncertainty
- Pareto frontier preservation
- counterfactual/adversarial branching
- proof obligations
- tail-risk/lower-tail evaluation
- regret and reversibility/option value
- invariant checking
- content-addressed evidence/authority lineage
- separation of speculative cognition from closure authority

The implementation deliberately does **not** copy Nolane World as a library dependency. D remains independently testable and deployable inside Nolane AI.

## Evaluation semantics

For each option and scenario, D computes:
- expected utility
- worst-case utility
- lower-tail utility over the worst 25% probability mass
- maximum scenario regret
- optionality from reversibility class
- a bounded robust helper score

The helper score is for ranking/inspection only. A selected option with declared objective vectors must still be on the Pareto frontier.

## Admission semantics

A decision is rejected when any blocker is present, including:
- stale/corrupted five-plane snapshot
- unresolved blocking proof obligation
- cross-plane traceability gap
- costly/irreversible decision with no explicit alternative
- costly/irreversible decision with no counterfactual/adversarial scenario
- costly-reversible decision with no rollback reference
- irreversible decision with unresolved high-risk uncertainty
- selected design option Pareto-dominated by another option

Successful admission emits a deterministic `DecisionReceipt`. Repeating the same decision against the same evidence and state yields the same receipt ID.

## Concurrency with A/B/C/... specialist agents

This architecture is designed for concurrent evolution. Other specialist agents may change their domains independently. D does not claim their authority. Instead, their effects enter D through explicit revision/digest references. When another specialist changes a dependency, the old D snapshot becomes stale and must be re-evaluated before new authority can be granted.

This is the intended coordination membrane between Goal/Design and the rest of Nolane AI.

## Files

- `nolane/external_core/goal_design.py` — goals, objectives, uncertainty, scenarios, options, Pareto/robust evaluation, snapshots, coherence, admission, receipts.
- `nolane/external_core/goal_design_contracts.py` — typed state contracts for all five D authorities.
- `nolane/external_core/goal_design_ledger.py` — append-only causal event ledger and authority separation.
- `cogcoder/organization/goal_design.py` — compatibility export surface.
- `tests/test_goal_design_coherence_plane.py`
- `tests/test_goal_design_contracts.py`
- `tests/test_goal_design_ledger.py`

## Next evolution boundaries

Future specialists can deepen each local D authority without breaking this layer. The stable integration surface is the state bundle + snapshot + decision receipt model. Local implementation details should not leak across plane boundaries.
