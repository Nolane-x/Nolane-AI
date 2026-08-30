# E. Acting — Canonical Refoundation Boundary

**Component family:** E  
**Revision:** 0.1.0 transactional baseline  
**Authority:** this document defines the intended ownership boundary for E while the branch is under review.

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

| E area | Canonical implementation | Responsibility |
|---|---|---|
| Invokable Cores | `nolane/external_core/invokable.py` | versioned core execution profile: schemas, capabilities, effects, permissions, failure/verification hooks, idempotency, retry, compensation |
| Execution Workspace | `nolane/external_core/execution_workspace.py` | isolated Git worktree + reversible local checkpoints + digest-proven restore |
| Executor | `nolane/external_core/acting_runtime.py` | transactional wrapper around concrete core invocation; checkpoint/invoke/verify/commit or restore/recover |
| Execution Control | `nolane/external_core/acting_protocol.py` | action lifecycle, leases, capability gates, effect budgets, idempotency, postcondition gates, rollback/degraded state, hash-chained receipts |

## Canonical flow

```text
upstream selected + authorized action
    -> execution contract
    -> capability-bounded lease
    -> precondition evidence
    -> effect-budget reservation
    -> concrete execution
    -> observed outcome
    -> postcondition verification
    -> COMMIT
       or ROLLBACK / DEGRADED
```

A concrete tool returning success is not enough to commit.

## Critical invariants

1. Forward effectful execution requires a live execution lease.
2. E cannot grant itself a missing capability.
3. Effect budgets are checked before invoking a core.
4. R4/irreversible execution requires an explicit recovery plan.
5. Commit requires postcondition verification at the minimum verifier level for the supplied risk class.
6. Local rollback is valid only when workspace restore reproduces the checkpoint digest.
7. External/irreversible failure is degraded unless domain-specific compensation is proven.
8. A committed idempotency key never re-invokes the side effect.
9. Lifecycle receipts are append-only and hash-chained.
10. E never performs candidate selection or strategic authorization.

## Compatibility

`nolane/external_core/execution.py` remains a compatibility controller because it currently combines neural decision generation with execution. The new E transactional boundary is intentionally separate so specialist work on C/D and other domains can evolve without E absorbing their ownership.

The later integration adapter should translate an upstream authorized decision artifact into the E execution contract and route its concrete core call through `TransactionalExternalCoreExecutor`.

## Verification

Dedicated CI: `.github/workflows/refoundation-e-acting.yml`

The gate compiles canonical E modules, runs E-specific protocol/workspace/executor contracts, and then executes every `tests/test_refoundation_*.py` test on Python 3.11 and 3.13. JUnit evidence is preserved on failures.

Full design rationale: `docs/superpowers/specs/2026-08-30-refoundation-e-acting-transactional-runtime-design.md`.
