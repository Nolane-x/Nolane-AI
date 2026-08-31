# CURRENT — F. Software Engineering

Date: 2026-08-31
Engineering wave: v0.8.0
Control-plane compatibility API: `external.software_engineering.control` v0.7.0
Effects state protocol: `external.software_engineering.effects` v0.1.0
Effect-journal protocol: `external.software_engineering.effect_journal` v0.1.0
Effect-recovery protocol: `external.software_engineering.effect_recovery` v0.1.0

The v0.8 wave changes the unified control-plane snapshot schema by adding durable external-effect acknowledgement history, so the control compatibility API advances from v0.6.0 to v0.7.0. The underlying effects ledger shape remains v0.1.0. The frozen `_software_engineering_control_v06` module is an internal compatibility implementation only; the public `software_engineering_control` module remains the single canonical cross-surface control entry point.

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
  -> prepared application intent
  -> external executor boundary under that immutable authorized intent
  -> durable observation-only executor acknowledgement
  -> local acknowledgement-backed finalization
  -> APPLIED + canonical application commit
  -> observe outcome
  -> postcondition evidence
  -> risk/surface-derived verification gate
  -> canonical Coding/Debug/UI receipt integrity
  -> cross-surface closure
  -> CANDIDATE_READY / candidate_only
  -> live current-validity revalidation

crash after external application acknowledgement but before local APPLIED transition
  -> restore durable application acknowledgement while transaction remains PRECONDITIONS_VERIFIED
  -> validate exact intent / mutation receipt / transaction / patch / application_ref lineage
  -> finalize local state only
  -> never invoke external application again

crash after APPLIED transition but before application-commit persistence
  -> exact acknowledgement / intent / transaction / patch / application_ref reconciliation
  -> reconstruct deterministic commit receipt only
  -> never invoke external application again

failure/recovery after mutation
  -> rollback intent
  -> external rollback executor boundary
  -> durable observation-only rollback acknowledgement
  -> independent restored-state verification
  -> acknowledgement + verification backed local completion
  -> ROLLED_BACK

crash after external rollback acknowledgement but before local ROLLED_BACK transition
  -> restore durable rollback acknowledgement while transaction is still recoverable
  -> require exact rollback intent / operation / target-state lineage
  -> require independent verification-testing proof
  -> finalize local rollback state only
  -> never invoke external rollback again

crash after ROLLED_BACK transition but before completion-receipt persistence
  -> exact acknowledgement / rollback intent / verification / operation_ref / reason reconciliation
  -> reconstruct deterministic rollback completion only
  -> never invoke external rollback again
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
- Mutation requires active exclusive bound claims and live precondition evidence at the mutation action boundary.
- Apply consumes an explicit content-addressed mutation-authority receipt; the unified control plane has no receipt-less apply path.
- External mutation is represented by a prepared application intent, an observation-only durable executor acknowledgement, and a canonical application commit; application references cannot be rebound across transactions.
- A durable application acknowledgement binds exact intent digest, transaction, patch, `application_ref`, executor namespace, executor receipt reference and observed-state digest.
- Successful acknowledgement retry is semantic-idempotent. Rebinding its intent, transaction, operation/idempotency reference, executor namespace, executor receipt or observed state fails closed.
- An acknowledgement is evidence that F observed an external executor response; it grants no mutation or recovery authority and therefore has authority exactly `observation_only`.
- If a crash occurs after F durably observes an application acknowledgement but before local transaction advancement, restart may finalize from `PRECONDITIONS_VERIFIED` without invoking the executor again.
- Application finalization rechecks the immutable mutation-authority receipt that authorized the observed effect lineage. It does not retroactively rerun live claim authorization after the acknowledgement has become historical fact.
- Later claim release blocks future mutation authority but does not erase a durable acknowledgement or an already-applied historical effect.
- The compatibility one-call `commit_application()` path still performs live mutation revalidation before it creates a new acknowledgement because that legacy call remains its action boundary.
- F does not independently authenticate external executor receipts and does not claim that a remote executor honors idempotency/query semantics. Those properties remain an executor-integration trust boundary.
- Therefore v0.8 guarantees acknowledgement-backed exactly-once **local finalization per immutable lineage**; it does not claim distributed exactly-once external execution.
- Claim scope is transaction-bound; unrelated claims owned by the same agent/task cannot authorize the transaction.
- Historical claim-state snapshots prove mutation authority at action time.
- Releasing a claim after successful apply is normal lifecycle and does not retroactively invalidate a technically valid candidate.
- Rollback becomes terminal only after independent verification proves the restored state matches the declared rollback target.
- A rollback acknowledgement must bind the exact rollback intent, transaction, patch, rollback operation and target-state digest, and its observed state must equal the declared target state.
- A durable rollback acknowledgement alone cannot complete rollback; successful local finalization also requires matching independent `verification-testing` proof.
- Compatibility `complete_rollback()` validates the verification receipt before it synthesizes its legacy acknowledgement, so a failed verification cannot manufacture historical rollback observation state.
- Required verification is derived from patch risk and sensitive surfaces, not chosen downward by the caller.
- Cross-surface receipts are canonical-codec validated before composition.
- Debug and UI receipts must share exact patch/Coding-readiness lineage when required.
- Historical closure is immutable; current validity is emitted separately.
- Positive terminal authority is `candidate_only`; mutation receipts are `mutation_scope_only`; rollback receipts are `recovery_scope_only`; executor acknowledgements are `observation_only`.
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

The unified `SoftwareEngineeringControlPlane` snapshot is content-addressed and includes work, immutable operation lineage, manifests, evidence, transactions, claim bindings, policy, mutation-authority history, effect intents/commits/completions, durable effect-journal acknowledgements, closure/gate history and current-validity history.

Restore is fail-closed on cross-layer lineage mismatch even when an attacker recomputes local and outer digests after tampering. Journal uniqueness indices are rebuilt from canonical acknowledgement rows rather than trusted as cache state. A canonical application commit requires its matching durable application acknowledgement; a canonical rollback completion requires its matching durable rollback acknowledgement. Removing either acknowledgement and recomputing the journal and outer digests still fails cross-ledger coverage validation.

A v0.6 unified control snapshot is not silently accepted as v0.7 because the missing acknowledgement history cannot be reconstructed truthfully. Schema migration, if introduced later, must be explicit and evidence-backed rather than inventing external observations.

## Validation gates

F acceptance requires the current PR merge-ref to pass:

- `Coding AGI Coding Organization Part V` on Python 3.11 and 3.13;
- `Nolane-AI Refoundation Epoch 0` on Python 3.11 and 3.13.

These gates must execute against current `main`, including independently upgraded subsystem work, before F is merged. Exact base/head/merge-tree identity must be rechecked immediately before merge.
