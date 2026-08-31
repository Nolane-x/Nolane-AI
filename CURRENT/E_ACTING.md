# E. Acting — Canonical Refoundation Boundary

**Component family:** E  
**Revision:** transactional baseline with canonical execution integration, fail-closed hardening, and crash-safe in-flight reconciliation  
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
| Invokable Cores | `nolane/external_core/invokable.py` | `0.0.2` | versioned core execution profile: schemas, capabilities, effects, permissions, failure/verification hooks, idempotency, retry, compensation |
| Execution Workspace | `nolane/external_core/execution_workspace.py` | `0.0.3` | isolated Git worktree + reversible local checkpoints + full-payload digest-proven restore, including ignored files and empty directories |
| Transaction Protocol | `nolane/external_core/acting_protocol.py` | `0.1.3` | lifecycle, lifecycle-bound modern leases, capability gates, effect budgets, idempotency, postcondition gates, rollback/degraded state, hash-chained receipts, legacy schema-1 restore enrichment, fail-closed interrupted-action reconciliation |
| Transactional Executor | `nolane/external_core/acting_runtime.py` | `0.1.2` | checkpoint/invoke/verify/commit or restore/recover around the concrete core executor, monotonic elapsed-time lease enforcement, and executor-free in-flight restart reconciliation |
| Canonical Execution Control | `nolane/external_core/execution.py` | `0.0.3` | compatibility-facing organization controller whose effectful tool path is forced through `TransactionalExternalCoreExecutor`; persists/restores the transactional ledger and conservatively classifies unconfined process tools |

## Canonical flow

```text
upstream selected + authorized action
    -> canonical Execution Control
    -> execution contract
    -> capability-bounded lease
    -> precondition evidence
    -> effect-budget reservation
    -> TransactionalExternalCoreExecutor
    -> concrete core execution
    -> observed outcome
    -> postcondition verification
    -> COMMIT
       or ROLLBACK / DEGRADED
    -> persisted receipt / ledger chain
```

A concrete tool returning success is not enough to commit. `OrganizationExecutionControlPlane.step()` no longer invokes the primitive executor directly for tool effects; it routes those effects through the transactional executor and then consumes the resulting core receipt for compatibility with the existing organization execution surface.

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
10. Modern lease acquisition, renewal, and revocation bind lease identity into immutable lifecycle evidence (`lease:<id>` and, for renewals, `previous-lease:<id>`). A persisted lease cannot be rebound by recomputing only its local identifier and record digest. Historical pre-binding schema-1 lease events remain loadable under their weaker compatibility semantics; E does not claim retroactive proof they never recorded.
11. E never performs candidate selection or strategic authorization.
12. Canonical execution control may infer only the minimum compatibility mapping needed to classify an already-selected tool action as read/local/external execution; it does not perform candidate or strategic reasoning.
13. Transactional ledger state is part of canonical execution-control persistence and is restored across runtime restart.
14. Lease validity after a core invocation is evaluated against monotonic elapsed runtime time; a slow core cannot reuse the acquisition timestamp to commit after TTL expiry.
15. Workspace rollback proof covers the complete worktree payload tree other than Git administrative metadata: tracked, untracked, ignored files, symlinks, directory entries, and empty directories all participate in the digest.
16. External-core classification dominates local mutation hints, preventing an external effect from being represented as locally reversible merely because mutation metadata is also present.
17. `terminal`, `compiler`, and `test-runner` are treated as external-like R3/V3 effects by the compatibility adapter because a disposable repository copy is not an operating-system sandbox; their failure therefore cannot be disguised as a no-effect read rollback.
18. Persisted non-terminal actions are never blindly resumed after process/runtime interruption. Pre-dispatch actions are cancelled; interrupted reads may be closed as explicit no-side-effect rollback; any mutating action at or beyond `EXECUTING` is degraded because completion and rollback evidence are not provable after restart. Reconciliation itself must not invoke the concrete executor.

## Crash-safe restart reconciliation

Persistence means an action can survive the process that started it. That is useful only if restart semantics do not create duplicate or falsely-recovered side effects. `TransactionalExternalCoreExecutor.reconcile_inflight(...)` therefore walks persisted records deterministically and delegates each non-terminal row to `ActingProtocolLedger.reconcile_interrupted(...)` without calling the concrete executor.

The recovery classification is deliberately asymmetric:

- `PROPOSED`, `LEASED`, and `PRECONDITION_VERIFIED` are pre-dispatch states, so interruption closes them as `CANCELLED` with explicit restart evidence.
- `EXECUTING`, `OUTCOME_OBSERVED`, and `POSTCONDITION_VERIFIED` reads are closed as `ROLLED_BACK` using a `no-side-effect:` evidence reference because the declared effect class is read-only.
- Mutating actions at or beyond `EXECUTING` become `DEGRADED`. A local mutation is not called rolled back because `RepositoryWorkspace` checkpoints are process-local temporary payloads; an external/irreversible effect is not retried because its completion may be unknown. Both cases require operator/domain recovery rather than duplicate execution.
- Terminal rows are left untouched, making repeated reconciliation idempotent.

Reconciliation is a recovery transition, not forward execution, so it does not require a still-live lease. It appends ordinary canonical terminal lifecycle events, preserving the existing schema-1 event-chain and record-digest validation model rather than inventing a parallel persistence format.

## Compatibility boundary

`nolane/external_core/execution.py` still contains the historical organization-facing inference/controller surface because upstream C/D refoundation is owned by other workstreams. That compatibility surface is no longer an execution bypass: its TOOL branch routes through `TransactionalExternalCoreExecutor`.

The adapter binds an already-issued `AgentDecisionReceipt` to the E contract via `authorization_ref`, derives a deterministic idempotency key from session + decision receipt, and conservatively maps external-core invocation first, then local workspace mutation, then genuinely read-only execution into E effect/risk classes. Unconfined process tools (`terminal`, `compiler`, `test-runner`) are explicitly elevated to external-like R3/V3 semantics. It does not mint strategic authorization or make a new candidate-selection decision.

`max_external_core_calls` remains an accounting limit for registered external-core invocations rather than a generic external-effect counter. External-like process tools are instead bounded by the transactional action effect budget and R3/V3 verifier requirement, keeping session accounting domains semantically distinct.

## Persistence authority

The E integration extends canonical runtime state with the transactional executor ledger. Runtime-state fingerprints are append-only provenance anchors rather than values to overwrite retroactively:

- Wave 1 and Wave 5N fingerprints remain historical anchors.
- Memory/Learning v0.0.5, governed promotion, and unified-B fingerprints remain historical anchors for the states they accepted.
- The original pre-B E Acting cutover fingerprint `eda96a54b833dee2a3eb2a3e697fb658f4ff73729fff76fa6746ba554a6d602e` remains historical evidence for the earlier E-only state.
- Integrating E Acting on top of the accepted unified-B/Memory runtime creates the current first-generation fingerprint `530054ed6d094c5ea000e38002346746ca63ddfb4d1c58b1d9f772263218415d`.
- That integrated fingerprint was observed identically on CPython 3.11.16 and 3.13.15 in an intentional RED run whose only Refoundation failure was the still-old unified-B fingerprint assertion; all other 645 Refoundation tests passed on each leg.
- Protocol `0.1.3` keeps acting schema version 1 for backward compatibility. It changes restart behavior rather than persisted shape: legacy digest-less records are still accepted only through full lifecycle projection validation and are emitted with a content digest on the next `to_state()`; modern lease transitions retain their stronger lifecycle evidence; interrupted rows are resolved by appending existing canonical terminal event types.

This preserves deterministic first-generation state while keeping every accepted persistence cutover independently auditable.

## Verification

Dedicated CI: `.github/workflows/refoundation-e-acting.yml`

The gate compiles canonical E modules, runs E-specific protocol/workspace/executor/crash-reconciliation contracts, and then executes every `tests/test_refoundation_*.py` test on Python 3.11 and 3.13. JUnit evidence is preserved on failures.

The canonical-integration regression contracts additionally require that:

- `OrganizationExecutionControlPlane.step()` contains the transactional invocation path and cannot directly call `self.executor.invoke(...)` for the canonical tool-effect path;
- `OrganizationExecutionControlPlane.to_state()` persists `acting_executor` state;
- `OrganizationExecutionControlPlane.from_state()` restores it with `TransactionalExternalCoreExecutor.from_state(...)`;
- core execution that consumes the lease TTL cannot subsequently commit using a stale timestamp;
- ignored payload and empty directories change workspace identity and participate in rollback proof;
- external effects take precedence over local rollback hints;
- unconfined process tools use the external-like R3/V3 verifier floor;
- schema-1 records without a local record digest restore only if the lifecycle projection remains valid and are enriched on reserialization;
- modern persisted lease identity remains bound to its acquisition/renewal/revocation lifecycle evidence even if an attacker recomputes local lease and record digests; and
- persisted in-flight actions reconcile without effect re-invocation: pre-effect rows cancel, read-only rows close with explicit no-side-effect rollback, and uncertain mutating rows degrade.

Full original design rationale: `docs/superpowers/specs/2026-08-30-refoundation-e-acting-transactional-runtime-design.md`.
Crash-reconciliation design rationale: `docs/superpowers/specs/2026-08-31-e-acting-crash-reconciliation-design.md`.
