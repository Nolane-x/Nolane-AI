# E. Acting — Canonical Refoundation Boundary

**Component family:** E  
**Revision:** transactional baseline with canonical execution integration and fail-closed hardening  
**Authority:** this document describes the implemented E ownership boundary on the E refoundation branch.

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
| Transaction Protocol | `nolane/external_core/acting_protocol.py` | `0.1.1` | lifecycle, leases, capability gates, effect budgets, idempotency, postcondition gates, rollback/degraded state, hash-chained receipts |
| Transactional Executor | `nolane/external_core/acting_runtime.py` | `0.1.1` | checkpoint/invoke/verify/commit or restore/recover around the concrete core executor, with monotonic elapsed-time lease enforcement |
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
9. Lifecycle receipts are append-only and hash-chained; persisted `ActionRecord` state is content-addressed and must project exactly from those lifecycle events.
10. E never performs candidate selection or strategic authorization.
11. Canonical execution control may infer only the minimum compatibility mapping needed to classify an already-selected tool action as read/local/external execution; it does not perform candidate or strategic reasoning.
12. Transactional ledger state is part of canonical execution-control persistence and is restored across runtime restart.
13. Lease validity after a core invocation is evaluated against monotonic elapsed runtime time; a slow core cannot reuse the acquisition timestamp to commit after TTL expiry.
14. Workspace rollback proof covers the complete worktree payload tree other than Git administrative metadata: tracked, untracked, ignored files, symlinks, directory entries, and empty directories all participate in the digest.
15. External-core classification dominates local mutation hints, preventing an external effect from being represented as locally reversible merely because mutation metadata is also present.
16. `terminal`, `compiler`, and `test-runner` are treated as external-like R3/V3 effects by the compatibility adapter because a disposable repository copy is not an operating-system sandbox; their failure therefore cannot be disguised as a no-effect read rollback.

## Compatibility boundary

`nolane/external_core/execution.py` still contains the historical organization-facing inference/controller surface because upstream C/D refoundation is owned by other workstreams. That compatibility surface is no longer an execution bypass: its TOOL branch routes through `TransactionalExternalCoreExecutor`.

The adapter binds an already-issued `AgentDecisionReceipt` to the E contract via `authorization_ref`, derives a deterministic idempotency key from session + decision receipt, and conservatively maps external-core invocation first, then local workspace mutation, then genuinely read-only execution into E effect/risk classes. Unconfined process tools (`terminal`, `compiler`, `test-runner`) are explicitly elevated to external-like R3/V3 semantics. It does not mint strategic authorization or make a new candidate-selection decision.

`max_external_core_calls` remains an accounting limit for registered external-core invocations rather than a generic external-effect counter. External-like process tools are instead bounded by the transactional action effect budget and R3/V3 verifier requirement, keeping session accounting domains semantically distinct.

## Persistence authority

The E integration extends canonical runtime state with the transactional executor ledger. Historical runtime-state digests remain immutable provenance anchors:

- Wave 1 accepted digest is preserved.
- Wave 5N planning/persistence cutover digest is preserved.
- E. Acting adds a new append-only runtime-state digest for the transactional-ledger cutover rather than rewriting either historical value.
- The post-hardening semantic component revisions do not mutate canonical first-generation runtime state; the accepted E runtime-state fingerprint therefore remains unchanged.

This preserves deterministic first-generation state while making idempotency and receipt-chain state restart-safe.

## Verification

Dedicated CI: `.github/workflows/refoundation-e-acting.yml`

The gate compiles canonical E modules, runs E-specific protocol/workspace/executor contracts, and then executes every `tests/test_refoundation_*.py` test on Python 3.11 and 3.13. JUnit evidence is preserved on failures.

The canonical-integration regression contracts additionally require that:

- `OrganizationExecutionControlPlane.step()` contains the transactional invocation path and cannot directly call `self.executor.invoke(...)` for the canonical tool-effect path;
- `OrganizationExecutionControlPlane.to_state()` persists `acting_executor` state;
- `OrganizationExecutionControlPlane.from_state()` restores it with `TransactionalExternalCoreExecutor.from_state(...)`;
- core execution that consumes the lease TTL cannot subsequently commit using a stale timestamp;
- ignored payload and empty directories change workspace identity and participate in rollback proof;
- external effects take precedence over local rollback hints; and
- unconfined process tools use the external-like R3/V3 verifier floor.

Full design rationale: `docs/superpowers/specs/2026-08-30-refoundation-e-acting-transactional-runtime-design.md`.
