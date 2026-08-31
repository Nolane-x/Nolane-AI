# E. Acting Crash-Safe In-Flight Reconciliation

## Problem

The transactional E boundary persists `ActionRecord` and lifecycle events across runtime restart. Before this hardening, persisted non-terminal rows could be restored but had no canonical transition out of `PROPOSED`, `LEASED`, `PRECONDITION_VERIFIED`, `EXECUTING`, `OUTCOME_OBSERVED`, or `POSTCONDITION_VERIFIED`. The ordinary idempotency replay path correctly refused to re-run an in-progress action, which prevented duplicate effects but could leave the action permanently stranded.

The unsafe alternative is automatic resume. After a process interruption E cannot generally distinguish these cases:

1. the concrete effect never started;
2. the effect started and failed before a receipt was persisted;
3. the effect completed but the receipt was lost before ledger transition;
4. a local mutation occurred but its process-local rollback checkpoint no longer exists;
5. an external or irreversible effect completed and must not be repeated.

Therefore restart recovery must preserve uncertainty instead of manufacturing success or rollback evidence.

## Authority

This mechanism belongs to E. Acting because it resolves execution lifecycle state after interruption. It does not choose a candidate, change a goal, create strategic authorization, or infer a new plan.

## State classification

### Pre-dispatch

`PROPOSED`, `LEASED`, and `PRECONDITION_VERIFIED` are before `begin_execution()`. E has not charged an attempt/effect budget and has not crossed the concrete executor boundary. On restart these rows are terminally `CANCELLED` with explicit interruption evidence.

### Read execution

A declared `READ` action at `EXECUTING`, `OUTCOME_OBSERVED`, or `POSTCONDITION_VERIFIED` may have consumed computation but by contract has no side effect. E closes it as `ROLLED_BACK` with a `no-side-effect:<evidence>` rollback reference. It does not auto-commit a previously verified read because the commit transition itself was not durably observed.

### Mutating execution

A `LOCAL_MUTATION`, `EXTERNAL_MUTATION`, or `IRREVERSIBLE` action at or after `EXECUTING` becomes `DEGRADED`.

For local mutation, `RepositoryWorkspace` checkpoint payloads are temporary process-local resources. Runtime restart destroys the proof needed to claim canonical restore, so E must not write a false `ROLLED_BACK` state.

For external and irreversible effects, outcome can be unknown and duplicate invocation may be harmful. Reconciliation therefore never retries or invokes a compensation implicitly.

## API

`ActingProtocolLedger.reconcile_interrupted(action_id, evidence_ref, reason)` performs the authoritative lifecycle transition. It requires evidence and a reason but no live lease because recovery must remain possible after lease expiry/revocation.

`TransactionalExternalCoreExecutor.reconcile_inflight(evidence_ref, reason)` deterministically scans persisted records, skips terminal rows, delegates each non-terminal row to the protocol, and returns the reconciled records. It never calls the concrete executor.

## Persistence and compatibility

The persisted schema remains version 1. Reconciliation emits the existing canonical `cancelled`, `rolled_back`, or `degraded` event types, so event-chain hashing, content-addressed record validation, and historical restore compatibility remain unchanged.

Component versions advance to:

- `external.acting.protocol` `0.1.3`
- `external.acting.runtime` `0.1.2`

## Safety invariants

1. Restart reconciliation never invokes an effect.
2. A row that never crossed `begin_execution()` is never recorded as having executed.
3. An interrupted read is never silently committed.
4. An interrupted mutating action is never declared rolled back without durable restoration proof.
5. Unknown external/irreversible outcome is never retried automatically.
6. Reconciliation is deterministic by action id and idempotent once rows are terminal.
7. Recovery remains possible even if the prior lease has expired or was revoked.
8. Every reconciliation result remains inside the existing append-only lifecycle/event-chain authority.

## Verification strategy

The dedicated crash-reconciliation regression begins from a persisted ledger and verifies:

- pre-effect interruption -> `CANCELLED` without attempt/effect counters;
- interrupted read -> `ROLLED_BACK` with explicit no-side-effect evidence;
- interrupted mutation -> `DEGRADED`, never false rollback/commit;
- runtime-wide reconciliation -> all in-flight rows terminalized deterministically without executor invocation;
- repeated runtime reconciliation -> no-op after closure.

The test is included both in the dedicated E contract set and in the full `tests/test_refoundation_*.py` matrix on CPython 3.11 and 3.13.
