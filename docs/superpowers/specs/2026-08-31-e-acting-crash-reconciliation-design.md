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

A second crash window exists above the acting ledger. The acting action may already be terminal, or even durably `COMMITTED`, while `OrganizationExecutionControlPlane` has not yet projected that result into its owning `ExecutionSession`. Leaving that session `RUNNING` would permit new inference over an execution history whose previous effect is unresolved at the control-plane layer.

## Authority

This mechanism belongs to E. Acting because it resolves execution lifecycle state after interruption. It does not choose a candidate, change a goal, create strategic authorization, or infer a new plan.

The acting ledger remains the effect-lifecycle authority. `OrganizationExecutionControlPlane` owns only the projection of that persisted effect history into its existing session/step/terminal receipt surfaces; it does not create a second acting state machine.

## State classification

### Pre-dispatch

`PROPOSED`, `LEASED`, and `PRECONDITION_VERIFIED` are before `begin_execution()`. E has not charged an attempt/effect budget and has not crossed the concrete executor boundary. On restart these rows are terminally `CANCELLED` with explicit interruption evidence.

### Read execution

A declared `READ` action at `EXECUTING`, `OUTCOME_OBSERVED`, or `POSTCONDITION_VERIFIED` may have consumed computation but by contract has no side effect. E closes it as `ROLLED_BACK` with a `no-side-effect:<evidence>` rollback reference. It does not auto-commit a previously verified read because the commit transition itself was not durably observed.

### Mutating execution

A `LOCAL_MUTATION`, `EXTERNAL_MUTATION`, or `IRREVERSIBLE` action at or after `EXECUTING` becomes `DEGRADED`.

For local mutation, `RepositoryWorkspace` checkpoint payloads are temporary process-local resources. Runtime restart destroys the proof needed to claim canonical restore, so E must not write a false `ROLLED_BACK` state.

For external and irreversible effects, outcome can be unknown and duplicate invocation may be harmful. Reconciliation therefore never retries or invokes a compensation implicitly.

### Committed acting result not yet projected to the session

If the acting ledger is already `COMMITTED`, restart recovery does not execute the action again. The control plane requires the persisted core receipt referenced by the acting row, verifies that it is successful, and reconstructs the missing `ExecutionStepReceipt` from durable receipt data. The owning session remains `RUNNING` because the action itself is known to have committed successfully.

This projection restores the session's core receipt/output references and tool accounting. Repeated reconciliation detects the existing decision/core step projection and becomes a no-op.

### Uncertain acting recovery projected to the session

After acting reconciliation, `DEGRADED` is projected to `ExecutionState.FAILED`; `CANCELLED` and `ROLLED_BACK` are projected to `ExecutionState.ABORTED`. The control plane uses its existing `_terminal()` primitive so recovery produces the ordinary content-addressed terminal evidence and receipt rather than a new persistence format.

Only the session identified by the acting contract's canonical idempotency key `execution-XXXXXXXX:<decision_receipt_id>` is terminalized. Unrelated sessions remain untouched.

## API

`ActingProtocolLedger.reconcile_interrupted(action_id, evidence_ref, reason)` performs the authoritative lifecycle transition. It requires evidence and a reason but no live lease because recovery must remain possible after lease expiry/revocation.

`TransactionalExternalCoreExecutor.reconcile_inflight(evidence_ref, reason)` deterministically scans persisted records, skips terminal rows, delegates each non-terminal row to the protocol, and returns the reconciled records. It never calls the concrete executor.

`OrganizationExecutionControlPlane.reconcile_interrupted_sessions(evidence_ref, reason)` projects acting recovery into canonical execution sessions. It first validates the complete set of control-plane-owned unprojected acting rows before mutating any row. An orphan session, decision-binding mismatch, non-running owner, or multiple unprojected actions for one session therefore fails closed without partially reconciling the ledger.

The control-plane method ignores acting rows whose idempotency key is not execution-session-shaped; E subcomponents may therefore retain independent acting records without being captured by organization-session recovery.

## Persistence and compatibility

The acting persisted schema remains version 1. Reconciliation emits the existing canonical `cancelled`, `rolled_back`, or `degraded` event types, so event-chain hashing, content-addressed record validation, and historical restore compatibility remain unchanged.

The control plane also introduces no new serialized field. Session, step, and terminal projections reuse existing `ExecutionSession`, `ExecutionStepReceipt`, and `ExecutionTerminalReceipt` state. `from_state()` remains a pure restore operation; recovery is explicit and auditable.

Component versions are:

- `external.acting.protocol` `0.1.3`
- `external.acting.runtime` `0.1.2`
- `external.execution.control` `0.0.4`

## Safety invariants

1. Restart reconciliation never invokes an effect.
2. A row that never crossed `begin_execution()` is never recorded as having executed.
3. An interrupted read is never silently committed.
4. An interrupted mutating action is never declared rolled back without durable restoration proof.
5. Unknown external/irreversible outcome is never retried automatically.
6. Reconciliation is deterministic by action id and idempotent once rows are terminal/projected.
7. Recovery remains possible even if the prior lease has expired or was revoked.
8. Every acting reconciliation result remains inside the existing append-only lifecycle/event-chain authority.
9. All control-plane ownership is preflighted before acting mutation, so one orphan cannot cause partial recovery of valid rows.
10. An acting row may recover only into the `ExecutionSession` and decision named by its persisted idempotency binding.
11. A recovery path never asks an inference backend for a new action and never calls the concrete executor's `invoke()` method.
12. An already-committed acting effect is projected from its persisted successful core receipt; it is never re-executed or converted into failure merely because the session step receipt was not persisted before the crash.
13. A normal acting row already represented by a matching decision/core `ExecutionStepReceipt` is treated as projected, including ordinary execution failures that subsequently terminalized the session.
14. Repeated control-plane recovery creates no duplicate step or terminal projection.
15. Deserialize/restore remains side-effect free; restart reconciliation is an explicit operation invoked by recovery authority.

## Verification strategy

The acting crash-reconciliation regression verifies:

- pre-effect interruption -> `CANCELLED` without attempt/effect counters;
- interrupted read -> `ROLLED_BACK` with explicit no-side-effect evidence;
- interrupted mutation -> `DEGRADED`, never false rollback/commit;
- runtime-wide reconciliation -> all in-flight rows terminalized deterministically without executor invocation;
- repeated runtime reconciliation -> no-op after closure.

The control-plane regressions additionally verify:

- only the owning execution session is terminalized;
- unrelated running sessions remain unchanged;
- orphan/session/decision mismatches fail before acting-ledger mutation;
- recovery is idempotent and does not touch inference/tool execution;
- a committed acting action missing only its session projection is reconstructed as a step receipt from the persisted core receipt;
- committed projection preserves a running session and correct tool/core/output accounting;
- repeated committed projection is a no-op.

All three recovery test surfaces are included in the dedicated E contract set and the full `tests/test_refoundation_*.py` matrix on CPython 3.11 and 3.13.
