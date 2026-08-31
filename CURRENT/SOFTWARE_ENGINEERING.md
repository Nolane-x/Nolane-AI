# CURRENT — F. Software Engineering

Date: 2026-08-31
Engineering wave: v0.7.0
Control-plane compatibility API: `external.software_engineering.control` v0.6.0
Effects state protocol: `external.software_engineering.effects` v0.1.0

The v0.7 wave changes crash/retry behavior without changing the serialized control/effects state schema, so compatibility identifiers remain stable rather than being bumped solely to mirror the engineering-wave number.

## Canonical authority

F has exactly five canonical component authorities:

1. `external.coding.claims`
2. `external.coding.patches`
3. `external.coding.control`
4. `external.debugging`
5. `external.ui_ux`

The `software_engineering*` modules are cross-surface composition/control protocols. Their internal identities are not canonical component registrations and do not add canonical write authority.

## Governed lifecycle

```text
patch + source claims + engineering operation_ref
  -> idempotent attempt initiation / immutable operation lineage
  -> change manifest
  -> immutable claim-state binding
  -> precondition evidence
  -> current mutation-authority receipt
  -> application intent
  -> consume receipt + revalidate live authority
  -> executor commit receipt
  -> observe outcome
  -> postcondition evidence
  -> risk/surface-derived verification gate
  -> canonical Coding/Debug/UI receipt integrity
  -> cross-surface closure
  -> CANDIDATE_READY / candidate_only
  -> live current-validity revalidation

crash after application state mutation but before commit-receipt persistence
  -> exact intent / transaction / patch / application_ref reconciliation
  -> reconstruct deterministic commit receipt only
  -> never re-run application mutation

failure/recovery after mutation
  -> rollback intent
  -> independent restored-state verification
  -> rollback completion

crash after rollback state mutation but before completion-receipt persistence
  -> exact rollback intent / verification / operation_ref / reason reconciliation
  -> reconstruct deterministic rollback completion only
  -> never re-run rollback mutation
```

## Critical invariants

- An explicit `operation_ref` is the idempotency key for one engineering attempt.
- Retrying an identical initiation under the same `operation_ref` returns the original work/transaction at its current phase without allocating a new transaction or replaying initiation mutations.
- Reusing an `operation_ref` with different immutable initiation inputs fails closed.
- Different `operation_ref` values may intentionally create independent attempts for the same patch; attempt fencing is not a global single-patch lock.
- Work records and patch transactions bind the same immutable operation lineage, and restore rejects cross-ledger operation rebinding even when outer state digests are recomputed.
- Successful engineering evidence cannot self-verify and must come from `verification-testing`.
- Evidence is bound to exact patch digest, source revision and environment.
- Revoking evidence or an upstream dependency invalidates dependent attestations without deleting history.
- Mutation requires active exclusive bound claims and live precondition evidence at the instant of apply.
- Apply consumes an explicit content-addressed mutation-authority receipt; the unified control plane has no receipt-less apply path.
- External mutation is represented by a prepared application intent and a committed executor receipt; application references cannot be rebound across transactions.
- If a crash occurs after the transaction reaches `APPLIED` but before its application commit is persisted, retry may finalize only when immutable mutation receipt, transaction, patch and `application_ref` lineage match exactly; otherwise it fails closed.
- Application reconciliation records an effect that has already happened. It does not re-run live mutation authorization or the external effect. Later claim release therefore blocks future mutation authority but does not erase an already-applied historical fact.
- Application reconciliation binds the executor receipt reference supplied by the external executor contract; F does not itself execute the effect or independently prove the external executor receipt's authenticity.
- Claim scope is transaction-bound; unrelated claims owned by the same agent/task cannot authorize the transaction.
- Historical claim-state snapshots prove mutation authority at action time.
- Releasing a claim after successful apply is normal lifecycle and does not retroactively invalidate a technically valid candidate.
- Rollback becomes terminal only after independent verification proves the restored state matches the declared rollback target.
- If a crash occurs after the transaction reaches `ROLLED_BACK` but before rollback completion is persisted, retry may finalize only when rollback intent, independent verification, rollback operation ref, target state and reason lineage all match; otherwise it fails closed.
- Rollback reconciliation never invokes rollback mutation a second time.
- Required verification is derived from patch risk and sensitive surfaces, not chosen downward by the caller.
- Cross-surface receipts are canonical-codec validated before composition.
- Debug and UI receipts must share exact patch/Coding-readiness lineage when required.
- Historical closure is immutable; current validity is emitted separately.
- Positive terminal authority is `candidate_only`; mutation receipts are `mutation_scope_only`; rollback receipts are `recovery_scope_only`.
- F owns no release, deployment, Assurance acceptance, capability promotion or repository canonical authority.

## Policy floor

Every candidate requires compile, test and static evidence.

Additional policy requirements:

- UI-sensitive: visual, responsive, accessibility, interaction;
- security-sensitive: security;
- performance-sensitive: performance;
- debug-origin: reproduction and root-cause evidence plus Debug closure;
- high/critical risk: independent review.

## State integrity

The unified `SoftwareEngineeringControlPlane` snapshot is content-addressed and includes work, immutable operation lineage, manifests, evidence, transactions, claim bindings, policy, mutation-authority history, external-effect history, closure/gate history and current-validity history.

Restore is fail-closed on cross-layer lineage mismatch even when an attacker recomputes local and outer digests after tampering. Attempt-idempotency indices are reconstructed from canonical work/transaction history rather than trusted as an unaudited cache. Reconciled application commits and rollback completions serialize through the same canonical histories as normally finalized effects; reconciliation creates no shadow state.

## Validation gates

F acceptance requires the current PR merge-ref to pass:

- `Coding AGI Coding Organization Part V` on Python 3.11 and 3.13;
- `Nolane-AI Refoundation Epoch 0` on Python 3.11 and 3.13.

These gates must execute against current `main`, including independently upgraded subsystem work, before F is merged.
