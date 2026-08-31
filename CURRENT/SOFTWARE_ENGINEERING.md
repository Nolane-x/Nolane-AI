# CURRENT — F. Software Engineering

Date: 2026-08-31
Engineering wave: v0.9.0
Control-plane compatibility API: `external.software_engineering.control` v0.8.0
Effects state protocol: `external.software_engineering.effects` v0.1.0
Effect-fencing protocol: `external.software_engineering.effect_fencing` v0.1.0
Effect-journal protocol: `external.software_engineering.effect_journal` v0.1.0
Effect-recovery protocol: `external.software_engineering.effect_recovery` v0.1.0
Effect-dispatch protocol: `external.software_engineering.effect_dispatch` v0.1.0
Recovery-frontier protocol: `external.software_engineering.recovery_frontier` v0.1.0

The v0.9 wave closes the remaining locally-provable crash window between a durable engineering intent and a durable external-executor acknowledgement. The unified control snapshot now contains durable pre-dispatch coordination history, so the public control compatibility API advances from v0.7.0 to v0.8.0. The frozen `_software_engineering_control_v07` module is an internal compatibility implementation only; the public `software_engineering_control` module remains the single cross-surface control entry point. The new dispatch and recovery-frontier protocols do not introduce canonical write authority and do not claim distributed exactly-once external execution.

## Canonical authority

F has exactly five canonical component authorities:

1. `external.coding.claims`
2. `external.coding.patches`
3. `external.coding.control`
4. `external.debugging`
5. `external.ui_ux`

The `software_engineering*` modules are cross-surface composition/control protocols. Their protocol identities are not canonical component registrations and do not add canonical write authority.

## Governed lifecycle

```text
patch + source claims + engineering operation_ref
  -> idempotent attempt initiation / immutable operation lineage
  -> change manifest
  -> immutable claim-state binding
  -> precondition evidence
  -> current mutation-authority receipt
  -> prepare exactly one application intent for the transaction
  -> transaction-scoped intent fence
  -> durable PRE_DISPATCH marker / coordination_only
  -> external executor boundary under immutable intent + namespace
  -> durable observation-only executor acknowledgement
  -> acknowledgement-backed local finalization
  -> APPLIED + canonical application commit
  -> observe outcome
  -> postcondition evidence
  -> risk/surface-derived verification gate
  -> canonical Coding/Debug/UI receipt integrity
  -> cross-surface closure
  -> CANDIDATE_READY / candidate_only
  -> live current-validity revalidation

restart before application dispatch marker
  -> recovery frontier = READY_TO_DISPATCH when live mutation authority remains valid

restart after PRE_DISPATCH but before durable acknowledgement
  -> recovery frontier = EXTERNAL_STATUS_REQUIRED
  -> automatic redispatch is forbidden
  -> integration must query/reconcile external status

restart after durable application acknowledgement but before APPLIED
  -> recovery frontier = LOCAL_FINALIZATION_READY
  -> validate exact dispatch / intent / acknowledgement / mutation lineage
  -> finalize local state only
  -> never invoke external application again

crash after APPLIED but before application-commit persistence
  -> exact acknowledgement / intent / transaction / patch / application_ref reconciliation
  -> reconstruct deterministic commit receipt only
  -> never invoke external application again

failure/recovery after mutation
  -> prepare exactly one rollback intent for the transaction
  -> transaction-scoped rollback-intent fence
  -> durable rollback PRE_DISPATCH marker / coordination_only
  -> external rollback executor boundary
  -> durable observation-only rollback acknowledgement
  -> independent restored-state verification
  -> acknowledgement + verification backed local completion
  -> ROLLED_BACK

restart after rollback PRE_DISPATCH but before acknowledgement
  -> recovery frontier = EXTERNAL_STATUS_REQUIRED
  -> automatic rollback redispatch is forbidden

restart after rollback acknowledgement but before independent verification
  -> recovery frontier = VERIFICATION_REQUIRED

restart after acknowledgement + independent verification
  -> recovery frontier = LOCAL_FINALIZATION_READY
  -> finalize rollback locally without invoking executor again

crash after ROLLED_BACK but before completion-receipt persistence
  -> exact acknowledgement / rollback intent / verification / operation_ref / reason reconciliation
  -> reconstruct deterministic rollback completion only
  -> never invoke external rollback again
```

## Critical invariants

### Attempt and scope integrity

- An explicit `operation_ref` is the idempotency key for one engineering attempt.
- Retrying identical initiation under the same `operation_ref` returns the original work/transaction at its current phase without allocating a new transaction or replaying initiation mutations.
- Reusing an `operation_ref` with different immutable initiation inputs fails closed.
- Different `operation_ref` values may intentionally create independent attempts for the same patch; attempt fencing is not a global single-patch lock.
- Work records and patch transactions bind the same immutable operation lineage; restore rejects cross-ledger rebinding even when local and outer digests are recomputed.
- Claim scope is transaction-bound; unrelated claims owned by the same agent/task cannot authorize the transaction.
- Historical claim-state snapshots prove mutation authority at the action boundary.

### Evidence and mutation authority

- Successful engineering evidence cannot self-verify and must come from `verification-testing`.
- Evidence is bound to exact patch digest, source revision and environment.
- Revoking evidence or an upstream dependency invalidates dependent attestations without deleting history.
- Mutation requires active exclusive bound claims and live precondition evidence at the mutation action boundary.
- Apply consumes an explicit content-addressed mutation-authority receipt; the unified control plane has no receipt-less apply path.
- Each transaction may prepare at most one immutable application intent. Exact retries return that intent; changing its application/idempotency ref or mutation-receipt lineage fails closed before dispatch.
- Each transaction may prepare at most one immutable rollback intent. Exact retries return that intent; changing rollback operation, reason or target state fails closed before dispatch.
- Transaction-intent fence indices are reconstructed from canonical intent rows at restore and are not independently trusted or serialized.

### Durable dispatch frontier

- `PRE_DISPATCH` is a durable coordination marker written before an integration crosses the external executor boundary.
- A dispatch marker has authority exactly `coordination_only`; it records local coordination history and does not grant executor, mutation, rollback, release or promotion authority.
- Application dispatch binds exact intent id/digest, transaction, patch, operation/application ref and executor namespace.
- Rollback dispatch additionally binds the exact rollback target-state digest.
- A transaction cannot own multiple dispatch records for the same effect kind; an operation ref cannot be rebound to another dispatch.
- Once a `PRE_DISPATCH` marker exists without a durable acknowledgement, F returns `EXTERNAL_STATUS_REQUIRED` and forbids automatic redispatch. This is the uncertainty frontier: the external effect may or may not have occurred.
- F does not invent an acknowledgement to escape uncertainty. An integration must query/reconcile the external executor and then record an actual observed acknowledgement.
- The recovery frontier is read-only and has authority exactly `advisory_only`.
- Application frontier states are `READY_TO_DISPATCH`, `EXTERNAL_STATUS_REQUIRED`, `LOCAL_FINALIZATION_READY`, `FINALIZED`, or `BLOCKED`.
- Rollback additionally uses `VERIFICATION_REQUIRED`; a rollback acknowledgement alone is never sufficient for local completion.

### Acknowledgement and local finalization

- External mutation is represented by prepared intent, durable dispatch lineage, an observation-only executor acknowledgement and a canonical application commit.
- A durable application acknowledgement binds exact intent digest, transaction, patch, application ref, executor namespace, executor receipt reference and observed-state digest.
- A rollback acknowledgement binds exact rollback intent, transaction, patch, rollback operation, executor namespace and target-state digest, and its observed state must equal the declared target state.
- Successful acknowledgement retry is semantic-idempotent. Rebinding intent, transaction, operation, executor namespace, executor receipt or observed state fails closed.
- Executor acknowledgements have authority exactly `observation_only`; they are evidence that F observed an external response, not authority to mutate.
- After a durable acknowledgement exists, local finalization may recover across restart without invoking the external executor again.
- Application finalization rechecks immutable mutation-receipt lineage that authorized the observed effect; later claim release blocks future mutation but cannot erase a durable historical acknowledgement.
- Rollback finalization still requires matching independent `verification-testing` proof of the declared restored state.
- A canonical application commit requires its acknowledgement and dispatch lineage; a canonical rollback completion requires acknowledgement, dispatch and independent verification lineage.

### Failure atomicity

- Backfilled `OBSERVED_WITH_ACK` dispatch history is written only after the corresponding acknowledgement/compatibility operation has succeeded.
- A denied compatibility application must leave both dispatch and acknowledgement histories unchanged.
- An invalid application acknowledgement must not create a dispatch marker.
- A failed rollback verification/completion must not create rollback dispatch or acknowledgement history.
- An invalid rollback acknowledgement must not create rollback dispatch history.
- Existing real `PRE_DISPATCH` history is never deleted merely because a later acknowledgement/finalization attempt fails; that dispatch is genuine uncertainty evidence and must remain queryable.
- Compatibility backfill is therefore failure-atomic: failed calls cannot manufacture historical dispatch facts.

### Authority boundaries and non-claims

- Dispatch records are `coordination_only`.
- Recovery-frontier receipts are `advisory_only`.
- Executor acknowledgements are `observation_only`.
- Application authority remains `mutation_scope_only`.
- Rollback authority remains `recovery_scope_only`.
- Positive terminal F authority remains `candidate_only`.
- F owns no release, deployment, Assurance acceptance, capability promotion or repository canonical authority.
- F does not independently authenticate external executor receipts and cannot prove a remote executor honors idempotency/query semantics.
- Therefore v0.9 provides a durable uncertainty frontier and exactly-once **local finalization per immutable acknowledged lineage**; it explicitly does not claim distributed exactly-once external execution.

## Policy floor

Every candidate requires compile, test and static evidence.

Additional policy requirements:

- UI-sensitive: visual, responsive, accessibility, interaction;
- security-sensitive: security;
- performance-sensitive: performance;
- debug-origin: reproduction and root-cause evidence plus Debug closure;
- high/critical risk: independent review.

## State integrity

The unified `SoftwareEngineeringControlPlane` snapshot is content-addressed and includes work, immutable operation lineage, manifests, evidence, transactions, claim bindings, policy, mutation-authority history, effect intents/commits/completions, durable effect-journal acknowledgements, durable dispatch records, closure/gate history and current-validity history.

Restore is fail-closed on cross-layer lineage mismatch even when an attacker recomputes local and outer digests after tampering. Journal uniqueness, intent fencing and dispatch indices are rebuilt from canonical rows rather than trusted as serialized cache state.

Every durable acknowledgement must have matching dispatch lineage. `OBSERVED_WITH_ACK` backfilled dispatch history must have a matching acknowledgement. Removing dispatch rows while retaining acknowledgements and recomputing digests fails restore. PRE_DISPATCH without acknowledgement remains legal and intentionally reconstructs `EXTERNAL_STATUS_REQUIRED` rather than being silently normalized away.

A v0.7 control snapshot is not silently accepted as v0.8 because durable dispatch history cannot be reconstructed truthfully. Schema migration, if introduced later, must be explicit and evidence-backed rather than inventing pre-dispatch observations.

## Validation gates

F acceptance requires the current PR merge-ref to pass:

- `Coding AGI Coding Organization Part V` on Python 3.11 and 3.13;
- `Nolane-AI Refoundation Epoch 0` on Python 3.11 and 3.13.

These gates must execute against current `main`, including independently upgraded subsystem work, before F is merged. Exact base/head/merge-tree identity must be rechecked immediately before merge.
