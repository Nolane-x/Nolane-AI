# E. Acting — Canonical Refoundation Boundary

**Component family:** E  
**Revision:** end-to-end execution proof continuity across core identity, workspace epochs, transactional dispatch, receipts, session persistence, and restart projection  
**Authority:** this document describes the implemented E ownership boundary on the canonical refoundation surface.

## Scope

E. Acting owns execution mechanics after an action has already been selected and authorized.

```text
E. Acting
├── Invokable Cores
├── Execution Workspace
├── Executor
└── Execution Control
```

E does not own goals, candidate synthesis, planning, architecture selection, causal inference, policy optimization, or strategic authorization.

## Canonical components

| E area | Canonical implementation | Version | Responsibility |
|---|---|---:|---|
| Invokable Cores | `nolane/external_core/invokable.py` | `0.0.3` | versioned core execution profile plus content-addressed `ExternalCoreSpec.contract_digest` identity |
| Execution Workspace | `nolane/external_core/execution_workspace.py` | `0.0.4` | isolated Git worktree, exclusive execution epochs, epoch/generation-bound checkpoints, and full-payload digest-proven restore |
| Concrete Executor | `nolane/external_core/execution_executor.py` | `0.0.2` | built-in/external core dispatch whose modern receipts bind the exact core contract and workspace execution epoch |
| Transaction Protocol | `nolane/external_core/acting_protocol.py` | `0.1.5` | lifecycle, lifecycle-bound modern leases, capability/effect budgets, idempotency, proof-bearing execution-contract identity, postcondition gates, rollback/degraded state, hash-chained receipts, and fail-closed restart reconciliation |
| Transactional Executor | `nolane/external_core/acting_runtime.py` | `0.1.5` | checkpoint/invoke/verify/commit or restore/recover around the concrete executor, monotonic lease enforcement, proof forwarding/receipt validation, and executor-free restart reconciliation |
| Canonical Execution Control | `nolane/external_core/execution.py` | `0.0.8` | session-level registry/epoch authority, transactional dispatch, proof-bearing step projection, persistence, restart validation, and control-plane reconciliation |

## Canonical flow

```text
upstream selected + authorized action
    -> canonical Execution Control
    -> proof-v2 execution session
       -> pin external-core registry digest
       -> claim exclusive workspace execution epoch
    -> execution contract
       -> bind exact external-core contract digest when applicable
       -> bind session workspace epoch
    -> capability-bounded lease
    -> precondition evidence
    -> effect-budget reservation
    -> TransactionalExternalCoreExecutor
    -> concrete core execution
    -> proof-bearing concrete receipt
    -> observed outcome
    -> postcondition verification
    -> COMMIT
       or ROLLBACK / DEGRADED
    -> proof-bearing step receipt
    -> persisted session / ledger chain
```

A concrete tool returning success is not enough to commit. `OrganizationExecutionControlPlane.step()` routes tool effects through `TransactionalExternalCoreExecutor`, verifies the concrete receipt against the selected action and persisted execution proof, then projects the accepted outcome into the session step chain.

## Critical invariants

1. Forward effectful execution requires a live execution lease.
2. E cannot grant itself a missing capability.
3. Effect budgets are checked before invoking a core.
4. R4/irreversible execution requires an explicit recovery plan.
5. Commit requires postcondition verification at the minimum verifier level for the supplied risk class.
6. Local rollback is valid only when workspace restore reproduces the checkpoint digest.
7. External/irreversible failure is degraded unless domain-specific compensation is proven.
8. A committed idempotency key never re-invokes the side effect.
9. Lifecycle receipts are append-only and hash-chained. Modern persisted `ActionRecord` state is content-addressed and cross-checked against lifecycle events; schema-1 records created before record digests existed may omit that local digest only when the lifecycle projection itself validates, and are enriched with a digest when reserialized.
10. Modern lease acquisition, renewal, and revocation bind lease identity into immutable lifecycle evidence (`lease:<id>` and, for renewals, `previous-lease:<id>`). Historical pre-binding schema-1 lease events remain loadable under their weaker compatibility semantics; E does not claim retroactive proof they never recorded.
11. E never performs candidate selection or strategic authorization.
12. Canonical execution control may infer only the minimum compatibility mapping needed to classify an already-selected tool action as read/local/external execution; it does not perform candidate or strategic reasoning.
13. Transactional ledger state is part of canonical execution-control persistence and is restored across runtime restart.
14. Lease validity after a core invocation is evaluated against monotonic elapsed runtime time; a slow core cannot reuse the acquisition timestamp to commit after TTL expiry.
15. Workspace rollback proof covers the complete worktree payload tree other than Git administrative metadata: tracked, untracked, ignored files, symlinks, directory entries, and empty directories all participate in the digest.
16. External-core classification dominates local mutation hints, preventing an external effect from being represented as locally reversible merely because mutation metadata is also present.
17. `terminal`, `compiler`, and `test-runner` are treated as external-like R3/V3 effects by the compatibility adapter because a disposable repository copy is not an operating-system sandbox; their failure therefore cannot be disguised as a no-effect read rollback.
18. Crash recovery is projected across the acting/control boundary: ownership is preflighted before mutation, uncertain recovered effects terminalize only their owning session, and already-committed effects are reconstructed as step receipts without re-invocation.
19. Persisted execution provenance is closed across session → decision → step/terminal ownership. Existing receipt IDs are not sufficient evidence: agent/backend/checkpoint/action-schema/step ordering and terminal snapshot bindings must agree before restored state is accepted.
20. Recovery binds the acting contract back to the exact selected tool action by `core_id`, `operation`, and canonical input digest before any acting mutation or terminal evidence write. A valid-looking `session:decision` idempotency key cannot authorize a semantically different effect.
21. Forward execution validates the concrete core receipt before outcome projection or commit. Agent, task, tool, operation, canonical input digest, authorization, and before/after workspace digests must all match the dispatched effect; substituted receipts fail closed through the existing rollback/degraded recovery path.
22. Persisted non-terminal actions are never blindly resumed after process/runtime interruption. Pre-dispatch actions are cancelled; interrupted reads may be closed as explicit no-side-effect rollback; any mutating action at or beyond `EXECUTING` is degraded because completion and rollback evidence are not provable after restart. Reconciliation itself must not invoke the concrete executor.
23. Risk authority is monotone with effect authority: READ requires at least R1, local mutation R2, external mutation R3, and irreversible effect R4. An execution contract cannot encode a weaker risk class than its effect class.
24. Physical effect classification is enforced again at the transactional runtime before any ledger or core mutation. Only bounded built-in reads are admitted as READ; filesystem writes are local mutations; process, external, custom, and unknown handlers are external-like by default. Caller-supplied effect/risk labels cannot downgrade this floor.
25. Modern execution sessions bind both the initial and current full workspace payload digest in provenance-v2 state. Reattachment requires the same base revision and the exact current payload digest; a same-revision substituted worktree is not execution authority.
26. Persisted step receipts form one workspace chain: every step's `before_workspace_digest` must equal the previous step's `after_workspace_digest`; modern session origin/frontier digests must agree with the first/last receipt.
27. Legacy execution sessions remain loadable for historical inspection and crash reconciliation but cannot resume forward execution. Stripping modern workspace-provenance fields therefore cannot downgrade a v2 session into effect authority. Normal commits and committed crash projections both advance the v2 current workspace fence.
28. Every newly started execution session is execution-proof-v2 and pins the exact `ExternalCoreRegistry.contract_digest`. Registry drift is rejected before context compilation, inference, acting-ledger mutation, or concrete dispatch; changing the registry requires a new session.
29. A registered external-core invocation is bound to the exact `ExternalCoreSpec.contract_digest` selected by the pinned registry. Built-in tools carry an empty core-contract digest and cannot impersonate an external-core contract.
30. One live `RepositoryWorkspace` can have only one execution-epoch owner. A second session cannot share or steal that epoch. Reclaim by the same owner is idempotent; restart attachment may bind only the exact persisted epoch after revision, payload, and registry fences validate.
31. Workspace checkpoints are bound to both `workspace_epoch_id` and checkpoint generation. Releasing an epoch invalidates its remaining checkpoints; a checkpoint from an old/released epoch cannot restore under a new owner or epoch.
32. Modern execution proof must agree end-to-end: session epoch → acting contract epoch → concrete core receipt epoch → execution step receipt epoch. For registered external cores, the acting contract, concrete receipt, and step receipt must also agree on the exact core-contract digest.
33. `ExecutionStepReceipt` includes proof fields in its canonical payload/digest. Changing the core-contract digest or workspace epoch therefore changes receipt identity and cannot be hidden behind the same step receipt ID.
34. Proof-v2 session serialization is explicit. If a persisted v2 session loses `external_core_registry_digest` or `workspace_epoch_id`, restoration fails closed instead of silently downgrading the record to proof-v1 authority.
35. Terminalization releases the session's workspace epoch only after terminal evidence/receipt and session state have been successfully projected. A mismatched or foreign epoch fails before release.
36. Control-plane restart reconciliation performs global proof preflight before acting-lifecycle mutation or committed projection. Registry drift, wrong epoch, substituted core receipt, or wrong core-contract identity prevents recovery from manufacturing forward authority.
37. Historical proof-v1 contracts/receipts remain loadable where their historical schemas can be validated, but omission of proof-v2 fields never grants modern forward execution authority or retroactive proof that the historical record never captured.

## Crash-safe restart reconciliation

Persistence means an action can survive the process that started it. `TransactionalExternalCoreExecutor.reconcile_inflight(...)` walks persisted records deterministically and delegates each non-terminal row to `ActingProtocolLedger.reconcile_interrupted(...)` without calling the concrete executor.

The recovery classification is deliberately asymmetric:

- `PROPOSED`, `LEASED`, and `PRECONDITION_VERIFIED` are pre-dispatch states, so interruption closes them as `CANCELLED` with explicit restart evidence.
- `EXECUTING`, `OUTCOME_OBSERVED`, and `POSTCONDITION_VERIFIED` reads are closed as `ROLLED_BACK` using a `no-side-effect:` evidence reference because the declared effect class is read-only.
- Mutating actions at or beyond `EXECUTING` become `DEGRADED`. A local mutation is not called rolled back because `RepositoryWorkspace` checkpoints are process-local temporary payloads; an external/irreversible effect is not retried because its completion may be unknown. Both cases require operator/domain recovery rather than duplicate execution.
- Terminal rows are left untouched, making repeated reconciliation idempotent.

At the execution-control layer, reconciliation first verifies the complete candidate set: owning session/decision, selected tool semantics, pinned registry, workspace epoch, and core-contract proof. A committed core outcome is projected only after its concrete receipt agrees with those persisted authorities. This preflight is global so an orphan or substituted row cannot partially mutate otherwise-valid acting history.

Reconciliation is a recovery transition, not forward execution, so it does not require a still-live lease. It appends ordinary canonical terminal lifecycle events, preserving the existing schema-1 event-chain and record-digest validation model rather than inventing a parallel persistence format.

## Compatibility boundary

`nolane/external_core/execution.py` still contains the historical organization-facing inference/controller surface because upstream C/D refoundation is owned by other workstreams. That compatibility surface is no longer an execution bypass: its TOOL branch routes through `TransactionalExternalCoreExecutor`.

The adapter binds an already-issued `AgentDecisionReceipt` to the E contract via `authorization_ref`, derives a deterministic idempotency key from session + decision receipt, and conservatively maps external-core invocation first, then local workspace mutation, then genuinely read-only execution into E effect/risk classes. Unconfined process tools (`terminal`, `compiler`, `test-runner`) are explicitly elevated to external-like R3/V3 semantics. It does not mint strategic authorization or make a new candidate-selection decision.

`max_external_core_calls` remains an accounting limit for registered external-core invocations rather than a generic external-effect counter. External-like process tools are instead bounded by the transactional action effect budget and R3/V3 verifier requirement, keeping session accounting domains semantically distinct.

## Persistence authority

The E integration extends canonical runtime state with the transactional executor ledger and proof-v2 execution-session fields. Runtime-state fingerprints are append-only provenance anchors rather than values to overwrite retroactively:

- Wave 1 and Wave 5N fingerprints remain historical anchors.
- Memory/Learning v0.0.5, governed promotion, and unified-B fingerprints remain historical anchors for the states they accepted.
- The original pre-B E Acting cutover fingerprint `eda96a54b833dee2a3eb2a3e697fb658f4ff73729fff76fa6746ba554a6d602e` remains historical evidence for the earlier E-only state.
- Integrating E Acting on top of the accepted unified-B/Memory runtime created the first-generation fingerprint `530054ed6d094c5ea000e38002346746ca63ddfb4d1c58b1d9f772263218415d`; that value remains historical evidence for the state it accepted rather than a proof-continuity identifier.
- Protocol `0.1.5` deliberately keeps acting schema version 1 for backward compatibility. Proof-bearing `ExecutionContract` fields are presence-sensitive: historical contracts omit both fields, while modern contracts serialize both. Legacy digest-less records are still accepted only through full lifecycle projection validation and are emitted with a content digest on the next `to_state()`.
- Modern execution sessions separately carry `execution_proof_version=2`, the pinned external-core registry digest, and their workspace epoch. Those fields are not inferred from absence and cannot be stripped to obtain forward authority.

This preserves independently auditable historical states while making new execution authority strictly stronger than the evidence available to earlier records.

## Verification

Dedicated CI: `.github/workflows/refoundation-e-acting.yml`

The gate compiles canonical E modules, runs the explicit E protocol/workspace/executor/crash-reconciliation/proof-continuity contracts, and then executes every `tests/test_refoundation_*.py` test on Python 3.11 and 3.13. `tests/test_refoundation_acting_session_proof_continuity.py` is part of the permanent explicit E invocation, so session registry/epoch authority cannot disappear while the broad suite remains accidentally green. JUnit evidence is preserved on failures.

The canonical-integration regression contracts additionally require that:

- `OrganizationExecutionControlPlane.step()` contains the transactional invocation path and cannot directly call `self.executor.invoke(...)` for the canonical tool-effect path;
- `OrganizationExecutionControlPlane.to_state()` persists `acting_executor` state and proof-v2 sessions/steps;
- `OrganizationExecutionControlPlane.from_state()` restores the transactional executor and fails closed on incomplete modern session/step proof;
- a new execution session pins the exact registry digest and claims an exclusive workspace epoch;
- a second live session cannot claim the same workspace epoch;
- registry drift fails before context compilation, inference, or concrete dispatch;
- restart attachment reclaims only the exact persisted epoch after revision/digest/registry validation;
- terminal transition releases the owning epoch;
- external-core receipts bind the exact `ExternalCoreSpec.contract_digest`, while built-ins cannot claim an external-core digest;
- acting contracts, core receipts, and step receipts agree on workspace epoch and external-core identity;
- changing step core/epoch proof changes the canonical step digest;
- stale checkpoints cannot cross execution epochs;
- recovery validates registry/session/acting/core proof globally before ledger mutation or committed projection;
- core execution that consumes the lease TTL cannot subsequently commit using a stale timestamp;
- ignored payload and empty directories change workspace identity and participate in rollback proof;
- external effects take precedence over local rollback hints;
- unconfined process tools use the external-like R3/V3 verifier floor;
- schema-1 records without a local record digest restore only if the lifecycle projection remains valid and are enriched on reserialization;
- modern persisted lease identity remains bound to its acquisition/renewal/revocation lifecycle evidence even if an attacker recomputes local lease and record digests;
- persisted in-flight actions reconcile without effect re-invocation: pre-effect rows cancel, read-only rows close with explicit no-side-effect rollback, and uncertain mutating rows degrade; and
- workspace provenance-v2 rejects same-revision payload substitution, enforces receipt-to-receipt digest continuity, advances the frontier on normal/recovered commits, and prevents legacy-state forward-execution downgrade.

Full original design rationale: `docs/superpowers/specs/2026-08-30-refoundation-e-acting-transactional-runtime-design.md`.  
Crash-reconciliation design rationale: `docs/superpowers/specs/2026-08-31-e-acting-crash-reconciliation-design.md`.  
Proof-continuity design rationale: `docs/superpowers/specs/2026-08-31-e-acting-proof-continuity-design.md`.
