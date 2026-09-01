# E. Acting End-to-End Proof Continuity Design

Date: 2026-08-31
Status: implementation design
Scope: E. Acting / Invokable Cores / Execution Workspace / Executor / Execution Control

## Context

The previous E closure made persisted execution graphs provenance-closed across session, decision, acting row, core receipt, step receipt, and terminal projection. It also introduced workspace provenance-v2 so a persisted execution session cannot reattach to a same-revision workspace with substituted payload.

One authority gap remains deliberately open: the proof chain does not yet bind the **versioned execution substrate** itself.

Today:

- `ExternalCoreSpec.contract_digest` exists, but neither `ExecutionSession`, `ExecutionContract`, nor `CoreInvocationReceipt` proves which concrete core contract governed an external invocation.
- a restored control plane accepts the caller-supplied `ExternalCoreRegistry` without proving that it is the registry authority under which a modern session began;
- `WorkspaceCheckpoint` proves workspace root + payload digest, but not the execution epoch that minted rollback authority;
- a checkpoint remains technically restorable while its snapshot exists, even if a later execution epoch has taken ownership of the same workspace object;
- `CoreInvocationReceipt` proves action identity and before/after workspace digests, but not the exact core-spec digest or workspace epoch that authorized dispatch;
- control-plane step/recovery projection therefore cannot close the proof chain over these two authority dimensions.

This design closes that gap without moving planning, strategy, candidate selection, or policy ownership into E.

Nolane World / runtime-assurance material is used only as an engineering reasoning lens. The relevant principles are version-bound authority, evidence scoped to the correct world revision, explicit stale-evidence rejection, and fail-closed recovery. Nolane AI gains no runtime import, schema dependency, or operational coupling to Nolane World.

## Design objective

For every modern effectful execution, E must be able to prove one continuous chain:

```text
selected ToolAction
    -> exact Invokable Core contract identity (when externally registered)
    -> exact workspace execution epoch
    -> acting ExecutionContract
    -> dispatch
    -> CoreInvocationReceipt
    -> workspace frontier
    -> ExecutionStepReceipt
    -> persisted ExecutionSession
    -> recovery / terminal projection
```

A digest is not merely metadata. If a field participates in authority, every downstream consumer must either reproduce it exactly or reject the transition.

## Threat and failure model

The wave must fail closed under:

1. **Core contract substitution** — an external core keeps the same `core_id` but the supplied registry contains a different version/capability/effect/permission/verification contract after restart.
2. **Receipt laundering across core versions** — a valid receipt for one core contract is projected as proof for a semantically different contract sharing the same tool id and input.
3. **Registry drift hidden by action identity** — `core_id`, operation, and input still match while the actual executable contract has changed.
4. **Stale checkpoint reuse** — a rollback checkpoint minted in execution epoch A is used after the same workspace has entered epoch B.
5. **Cross-session workspace authority** — two live sessions silently share one workspace object and independently mint rollback authority.
6. **Epoch stripping downgrade** — modern persisted state loses epoch fields and is interpreted as an older but forward-authoritative form.
7. **Recovery projection from wrong epoch** — a committed acting row references a core receipt whose workspace epoch is not the owning session epoch.
8. **Legacy compatibility confusion** — historical receipts remain loadable, but their lack of new proof fields must never become new forward-execution authority.

The design does not claim protection against an attacker who can replace the trusted runtime/code itself. It provides deterministic internal consistency and fail-closed authority boundaries.

## 1. Invokable Core identity

### 1.1 Per-core contract digest is the authority unit

`ExternalCoreRegistry.contract_digest` remains useful for inventory integrity, but execution binds the **selected core**, not the whole registry. Global registry binding would unnecessarily invalidate unrelated sessions when an unrelated core is added.

For an externally registered `tool_id`, E resolves:

```text
core_contract_digest = external_cores.get(tool_id).contract_digest
```

Built-in canonical tools (`filesystem`, bounded `git`, `code-search`, and process-tool adapters) are not represented by `ExternalCoreSpec`; they use an empty external-core contract digest and remain governed by their code/version + physical-effect classification rules. This wave does not invent fake ExternalCoreSpec rows for built-ins.

### 1.2 Modern session registry fence

A modern `ExecutionSession` gains:

- `execution_proof_version = 2`;
- `external_core_registry_digest` — digest of the registry snapshot visible at session start;
- `workspace_epoch_id` — immutable identity of the workspace execution epoch.

The registry digest protects restored modern state from wholesale caller-supplied registry substitution. Per-action core digests prevent an unrelated registry addition from changing the semantic identity of historical receipts.

Forward execution requires the current registry digest to equal the session fence. A changed registry requires a new execution session; E does not silently migrate authority mid-session.

Legacy sessions remain inspectable/reconcilable under their existing rules but cannot become modern forward-authoritative by omission of these fields.

## 2. Workspace execution epoch

### 2.1 Epoch lifecycle

`RepositoryWorkspace` owns an in-memory execution-epoch lease:

```text
claim_execution_epoch(owner_id) -> workspace_epoch_id
release_execution_epoch(owner_id, workspace_epoch_id)
```

Properties:

- only one owner may hold the workspace epoch at a time;
- claiming an already-owned epoch by another session fails;
- re-claim by the same owner returns the existing epoch id;
- epoch identity is derived from workspace identity + monotonic epoch generation + owner;
- a released epoch can never be resurrected; the next claim receives a new generation/id;
- closing the workspace invalidates the active epoch.

`OrganizationExecutionControlPlane.start()` claims the workspace epoch before the new session becomes authoritative. `attach_workspace()` claims/rebinds the persisted epoch only when the workspace is not currently owned by another session and the persisted workspace fence matches.

Terminalization releases the execution epoch after the final session state is persisted. A terminal session cannot use the released epoch for forward execution.

### 2.2 Checkpoint fencing

`WorkspaceCheckpoint` gains:

- `workspace_epoch_id`;
- `checkpoint_generation`.

`checkpoint()` requires an active execution epoch and embeds both fields into checkpoint identity.

`restore()` and `release_checkpoint()` require:

- the checkpoint belongs to the current workspace root;
- its snapshot still exists;
- its `workspace_epoch_id` equals the currently active epoch;
- checkpoint generation is recognized as belonging to that epoch.

Therefore a snapshot copied from or retained by an earlier epoch cannot regain rollback authority after a new session claims the workspace.

The snapshot remains ephemeral; this wave does not make local checkpoints durable across process restart. Crash semantics stay conservative: uncertain local mutation after restart is still degraded, not fabricated as rolled back.

## 3. Acting contract continuity

`ExecutionContract` gains optional proof fields for backward-compatible restoration:

- `core_contract_digest`;
- `workspace_epoch_id`.

They participate in `semantic_payload()` and therefore in idempotency conflict detection.

New transactional invocations require an explicit non-empty `workspace_epoch_id`. For an externally registered core they also require an explicit `core_contract_digest`; built-in tools use the canonical empty value because they have no ExternalCoreSpec row.

The acting ledger remains schema-compatible at the container level: historical rows that omit these fields can be restored. However a historical row lacking modern proof fields cannot be treated as a newly-authorized modern dispatch.

## 4. Executor receipt continuity

`CoreInvocationReceipt` gains:

- `core_contract_digest`;
- `workspace_epoch_id`.

Both fields are included in the receipt payload/digest for new receipts.

`ExternalCoreExecutor.invoke()` accepts the expected proof context from the transactional executor. Before dispatch it verifies:

- the workspace currently exposes the expected active epoch;
- for an external core, the registry’s current per-core digest equals the expected digest;
- for a built-in tool, expected external-core digest is empty.

The persisted receipt therefore attests which core contract and workspace epoch actually governed dispatch.

Historical receipts lacking these fields remain deserializable in legacy form. They cannot satisfy modern receipt validation for a new/provenance-v2 execution.

## 5. Transactional runtime validation

`TransactionalExternalCoreExecutor.invoke()` receives:

- `core_contract_digest`;
- `workspace_epoch_id`.

It puts them into the `ExecutionContract`, forwards them to the concrete executor, and extends `_validate_core_receipt()` to require exact equality.

This validation happens before outcome projection and commit. A substituted receipt from the wrong core version or workspace epoch therefore follows the existing fail-closed recovery path and cannot commit.

Local mutation checkpoints are created only after the epoch proof has been validated, so rollback authority is born inside the same execution proof chain as dispatch.

## 6. Execution Control continuity

### 6.1 Start / attach

At `start()`:

1. verify current task/backend/workspace requirements;
2. claim a workspace epoch for the to-be-created session owner;
3. snapshot the current external-core registry digest;
4. mint a modern proof-v2 session with both fences;
5. publish session + attached workspace only after all fields exist.

If construction fails after claim, the epoch is released.

At `attach_workspace()`:

1. verify base revision and workspace payload frontier;
2. verify modern registry fence against current `ExternalCoreRegistry`;
3. claim/rebind the exact persisted workspace epoch;
4. reject a workspace already owned by another live execution session.

### 6.2 Step

Before inference and again immediately before transactional dispatch, modern sessions verify:

- workspace digest frontier;
- active workspace epoch id;
- registry digest fence.

For TOOL action:

- external registered tool → resolve exact `ExternalCoreSpec.contract_digest`;
- built-in tool → empty digest;
- pass both core digest + epoch into transactional invocation;
- consume only a core receipt reproducing both values.

`ExecutionStepReceipt` gains `core_contract_digest` and `workspace_epoch_id`. They are part of its digest and are cross-validated against the owning session and persisted core receipt during state validation.

### 6.3 Recovery

Global recovery preflight adds:

- acting contract epoch must equal session epoch;
- committed core receipt epoch must equal session epoch and acting contract epoch;
- acting/core per-core contract digest must agree;
- when the core remains present in the current registry, its digest must equal the historical contract digest;
- session registry fence must equal the current registry digest before a committed effect can be projected into a resumable RUNNING session.

If registry drift is detected, E must not project a committed action into fresh forward authority. The row/session is rejected for operator-controlled reconciliation rather than silently upgrading its execution substrate.

## 7. Persistence and compatibility

Compatibility is deliberately asymmetric.

### Historical state

- existing session workspace provenance v1/v2 remains loadable;
- old acting contracts and core/step receipts remain loadable;
- crash reconciliation may inspect and conservatively terminalize historical rows under existing semantics;
- historical state does not acquire proof-v2 forward authority.

### New state

Every newly created session is execution-proof v2 and requires:

- registry digest fence;
- workspace epoch id;
- modern core/step receipt proof fields.

Field stripping from proof-v2 state must fail restoration, not downgrade it.

## 8. Error handling and atomicity

The wave preserves E’s current fail-closed ordering:

- authority checks occur before side effects;
- full recovery ownership/proof preflight occurs before ledger mutation;
- checkpoint rollback never crosses epoch boundaries;
- a core receipt mismatch is handled as an execution failure before commit;
- terminalization releases workspace epoch only after terminal state exists;
- start/attach failures must not leak a claimed epoch.

No automatic re-invocation is added.

## 9. Component versioning

Expected semantic bumps:

- `external.invokable_cores`: `0.0.2` → `0.0.3` (contract identity becomes execution authority);
- `external.execution.workspace`: `0.0.3` → `0.0.4` (execution epochs + checkpoint fencing);
- `external.execution.executor`: `0.0.1` → `0.0.2` (receipt carries core/epoch proof);
- `external.acting.protocol`: `0.1.4` → `0.1.5` (execution contract proof fields);
- `external.acting.runtime`: `0.1.4` → `0.1.5` (dispatch/receipt proof validation);
- `external.execution.control`: `0.0.7` → `0.0.8` (session/step/recovery proof closure).

Version updates happen only after RED contracts prove old behavior is insufficient.

## 10. TDD acceptance contract

RED must prove at least these old-code failures:

1. a session can start without pinning registry identity;
2. restored modern execution accepts a substituted external-core registry;
3. a core receipt can omit/lie about core contract identity and still pass current provenance checks;
4. a core receipt can omit/lie about workspace epoch and still pass;
5. the same workspace object can be started by two execution sessions without an epoch ownership conflict;
6. a checkpoint from an earlier workspace execution epoch can be restored after a newer epoch is claimed;
7. persisted step/core/acting records can disagree on core-contract or epoch proof because those fields do not exist today;
8. recovery can project a committed receipt without proving the session/core/acting epoch chain.

GREEN requires:

- targeted proof-continuity tests pass;
- all existing E acting tests pass;
- full `tests/test_refoundation_*.py` passes on Python 3.11 and 3.13;
- canonical modules compile;
- `git diff --check` passes;
- exact integration head against latest `main` is accepted before merge.

## 11. Non-goals

- No durable restoration of process-local workspace checkpoints.
- No distributed workspace lock service.
- No planning, candidate synthesis, strategic authorization, or policy migration into E.
- No fake ExternalCoreSpec wrappers for canonical built-in tools.
- No automatic migration of an active session to a changed core registry.
- No claim that a digest proves semantic correctness beyond the exact contract bytes it binds.
- No Nolane World runtime dependency.

## 12. Resulting invariant

After this wave, a modern E commit is accepted only when the selected action, invokable contract, workspace epoch, acting lifecycle, concrete receipt, workspace frontier, step projection, and persisted session all name the same execution reality.

That is the E. Acting proof-continuity boundary.
