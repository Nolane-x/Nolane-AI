# Goal/Design Assumption Truth-Maintenance

## Purpose

D. Goal / Design decisions often depend on assumptions that can become unsupported, contested, or refuted while Requirements, Planning, Architecture, Integration, and Context remain otherwise unchanged. This subsystem makes those assumptions explicit decision dependencies and binds their exact state into Goal/Design authority.

It is deliberately **not** a sixth Family-A Truth / Knowledge component. Family A remains the canonical owner of `external.evidence`, `external.knowledge`, `external.epistemic`, `external.verification`, and `external.assurance`. Goal/Design owns only the decision-specific assumption model used to decide whether a D receipt remains valid.

`nolane.external_core.goal_design_truth` therefore declares no `COMPONENT_ID` and must not be treated as a replacement for canonical Family-A evidence or knowledge.

## Authority boundary

The boundary is:

```text
Family A canonical Truth / Knowledge
    └─ authoritative evidence / knowledge / epistemic / verification / assurance state

D Goal / Design
    └─ decision-local assumption graph
         ├─ assumption identifiers and dependency edges
         ├─ references to provenance (`evidence_ref`)
         ├─ derived decision-local status
         └─ exact assumption snapshot bound to DecisionReceipt v3
```

An `AssumptionEvidence` row is a D projection input. Its `evidence_ref` is a provenance reference, not a claim that D owns the referenced global truth. Future bridges may validate those references against Family-A `EvidenceLedger` / scoped Truth state, but D must consume or project canonical A authority rather than seize it.

## First-class assumptions

`GoalSpec.assumption_refs` and `DesignOption.assumption_refs` are stable identifiers. They are intentionally separate from legacy free-form `assumptions` text.

`AssumptionClaim` provides:

- a stable `assumption_id`;
- human-readable statement;
- criticality;
- transitive `depends_on` edges;
- optional Requirement / Plan / Architecture / Integration trace refs;
- content-addressed identity.

The graph fails closed on unknown dependencies and cycles.

## Evidence and status

D assumption evidence is append-only at the semantic boundary. Evidence can support or refute an assumption with bounded confidence. Retraction never deletes history; it creates an immutable retraction record.

Direct status is derived from active evidence:

- `UNKNOWN`
- `SUPPORTED`
- `CONTESTED`
- `REFUTED`

Effective status also includes transitive dependencies. A supported child becomes effectively refuted when a required parent is refuted; dependency evidence is not rewritten or laundered into the child.

Snapshots bind the complete transitive closure, assessment digests, evidence/retraction state, and therefore change whenever relevant truth state changes.

## DecisionReceipt v3

DecisionReceipt v3 is a monotonic extension of the existing v2 proof-carrying receipt.

A v3 receipt requires:

- the complete v2 manifest;
- canonical `assumption_refs`;
- `assumption_state_digest` for the exact transitive assumption snapshot.

Partial v3 state fails closed. v1 and v2 receipts retain their historical identities and are not retroactively bound to assumptions.

To preserve exact historical identities, the pre-v3 implementations are frozen in:

- `nolane/external_core/_goal_design_base.py`
- `nolane/external_core/_goal_design_runtime_base.py`

The public `goal_design.py` and `goal_design_runtime.py` layers extend those frozen semantics rather than silently recomputing old receipt identities under a new dataclass schema.

## Complete evaluated-option binding

Robust evaluation, max-regret and Pareto reasoning compare the full option set. Therefore a truth-bound receipt binds assumptions from:

1. the GoalSpec; and
2. **every evaluated DesignOption**, including alternatives.

This prevents a receipt from claiming to represent one evaluation while its identity only binds the selected option's world assumptions.

Known-refuted assumptions are fail-closed even when they belong to an alternative, because a refuted alternative cannot remain a valid semantic input to regret/Pareto comparison. For unsettled but not refuted state, admission remains reversibility-sensitive according to `DecisionClass`.

## Admission policy

The assumption policy is deliberately asymmetric by reversibility:

- `REVERSIBLE`: UNKNOWN/CONTESTED may proceed, REFUTED blocks.
- `COSTLY_REVERSIBLE`: unsettled high-criticality assumptions block; REFUTED always blocks.
- `IRREVERSIBLE`: referenced assumptions must be SUPPORTED; REFUTED always blocks.

A truth-bound Goal/Design decision cannot be admitted without an assumption truth-maintenance provider. Missing authority fails closed.

## Runtime invalidation

`GoalDesignRuntime.apply_assumption_change()` performs an explicit authority transition:

1. validate the changed assumption IDs;
2. compute transitive affected-assumption closure;
3. derive affected Requirement / Plan / Component / Integration refs;
4. mint typed `ASSUMPTION_CHANGE` authority in the Goal/Design causal ledger;
5. find active v3 decisions whose bound assumption closure intersects the affected closure;
6. transition only those decisions to `STALE`;
7. mint `INVALIDATION` events with both the original decision authority event and the assumption-change authority event as causal parents.

Unrelated assumption changes do not invalidate a decision.

`revalidate_decisions()` independently recomputes each active v3 assumption snapshot. If the digest no longer matches, or the truth-maintenance provider is unavailable, the receipt becomes stale. Historical v1/v2 receipts are not retroactively attached to this mechanism.

## Persistence and tamper resistance

The decision authority index persists both:

- `assumption_refs`
- `assumption_state_digest`

Restored receipts pass the same schema-aware authenticity verifier as newly minted receipts. Rebinding assumption refs or the assumption digest while retaining the old receipt ID therefore fails with an identity digest mismatch.

The assumption graph itself persists content digests for claims, evidence and retractions. Restore validates those digests before accepting state.

## Causal ledger semantics

V3 DECISION events bind assumption refs and assumption-state digest in both their payload and subject set. Truth changes are typed `AUTHORITY`, not generic observations. This preserves the distinction between:

- thought;
- evidence;
- admitted decision authority;
- explicit withdrawal of authority.

## Concurrency rule

D does not write Requirements, Planning, Architecture, Integration, Context, or Family-A Truth / Knowledge state. Other specialist agents remain canonical writers for their domains. D only observes those authorities, owns its decision receipts and lifecycle, and invalidates D authority when a dependency it explicitly bound has changed.

This rule is essential for safe concurrent development of Nolane AI.