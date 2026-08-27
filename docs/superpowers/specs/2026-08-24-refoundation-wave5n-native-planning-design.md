# Refoundation Epoch 0 Wave 5N — Native Planning Design

## Status

Design freeze for the Wave 5N native Planning cutover. This wave starts from the accepted Wave 5M Requirements head and must preserve the repository authority model, historical provenance, deterministic state, and zero-loss compatibility.

## Objective

Move executable authority for `external.planning` from `cogcoder.organization.planning` into `nolane.external_core.planning` while eliminating the currently duplicated mutable plan-revision authority.

The canonical invariant after this wave is:

> `MasterPlanGraph.version` is the only mutable plan-revision clock. `TaskGraph.plan_version` is a read-only projection of that authority.

Native-debt target: 32 -> 31, removing only `external.planning`.

## Semantic boundary

Wave 5N owns:

- `PlanNodeStatus`, `PlanNode`, `Milestone`, `PlanRisk`, `PlanRevision`, `PlanDelta`, `GapApplication`;
- `MasterPlanGraph` and `PlanningControlPlane`;
- plan revision, rollback, gap-application, task-link and delta semantics;
- synchronization of the TaskGraph plan-revision projection;
- persistence rules needed to prove a single plan-revision authority;
- exact historical Planning import compatibility.

Wave 5N does not redesign:

- `external.architecture`;
- lease/fencing authority;
- Requirements semantics accepted in Wave 5M;
- execution/coding/debugging control planes;
- historical evidence or archive placement.

## Single revision authority

### Canonical clock

`MasterPlanGraph.version` remains derived from its append-only revision ledger. Applying a revision, applying a plan gap, or rolling back creates exactly one new canonical plan revision.

### TaskGraph projection

`TaskGraph` must no longer increment a local plan counter. In organization.tasks v0.0.2:

- fresh `plan_version` is 0;
- `plan_version` is exposed read-only;
- a private Planning-owned projection operation may advance it to the exact canonical graph version;
- backward projection is rejected;
- Planning projects both revision number and authoritative plan-node IDs after every successful plan mutation;
- the legacy `TaskGraph.apply_plan_amendment` public entrypoint remains available, but delegates through a bound Planning authority and cannot mutate revision state by itself.

The TaskGraph component revision therefore advances from 0.0.1 to 0.0.2 because its persistence and mutation semantics change even though its canonical module remains `nolane.organization.tasks`.

## Persistence and migration

New TaskGraph state carries:

`plan_revision_authority: external.planning`

Canonical/marked state is strict: when a Planning graph and TaskGraph are composed, their revisions must match or restore fails closed.

Historical TaskGraph state did not carry this marker and initialized its local clock to 1 while a fresh historical `MasterPlanGraph` initialized to 0. To preserve zero-loss restore without institutionalizing two clocks, only the known empty historical bootstrap mismatch is normalized:

- legacy/unmarked TaskGraph revision 1 + empty Planning graph revision 0 -> canonical projection 0.

Any other unexplained legacy mismatch is rejected. A matching legacy revision may be adopted and then marked canonical by composition.

This compatibility rule is intentionally narrow and must not become a general version-rewrite mechanism.

## Legacy amendment compatibility

`TaskGraph.apply_plan_amendment(...)` remains callable for accepted historical callers. It is not authority.

When a PlanningControlPlane is bound, the compatibility call:

1. validates the referenced `PLAN_GAP_DETECTED` event;
2. routes master-plan write authorization through Planning;
3. converts the requested node IDs into canonical PlanNodes;
4. records exactly one `MasterPlanGraph` revision;
5. projects the resulting revision and node set back to TaskGraph;
6. emits the accepted amendment event semantics;
7. returns that event.

If no Planning authority is bound, the compatibility call fails closed instead of reverting to a local mutation clock.

## Ownership and bridge

After cutover:

- canonical implementation: `nolane.external_core.planning`;
- historical source: `cogcoder/organization/planning.py` becomes an exact public-object compatibility/provenance bridge;
- `external.planning` becomes canonical-native at 0.0.1 with canonical write authority;
- `external.planning` is removed from active facade bindings and generated native debt;
- no canonical Planning source may reverse-import `cogcoder.organization.planning`.

## Acceptance gates

Wave 5N is accepted only when all of the following hold on one exact clean source head:

1. TDD RED proves the pre-cutover ownership and dual-clock defects.
2. Canonical and historical public Planning symbols are exact identities.
3. TaskGraph cannot independently mutate plan revision.
4. apply, rollback and gap paths keep TaskGraph projection equal to MasterPlanGraph.version.
5. marked persistence mismatch fails closed.
6. the single known legacy bootstrap mismatch normalizes deterministically.
7. component/version/facade/implementation ledgers agree.
8. repository audit regenerates native debt at 31 without hand-edited generated truth.
9. full Refoundation contracts and zero-loss evidence pass.
10. organization/campaign/execution regressions pass.
11. frozen Neural R2.3 metadata remains unchanged.
12. no temporary write-enabled migration carrier remains in the accepted head.

No auto-merge is permitted.