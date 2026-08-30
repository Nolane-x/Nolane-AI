# Refoundation E. Acting — Transactional Runtime Design

**Date:** 2026-08-30  
**Scope owner:** `E. Acting` only  
**Status:** implemented architecture baseline (`0.1.x`)  
**Branch:** `refoundation/e-acting-transactional-runtime-gpt56sol`

## 1. Why E. Acting needs a separate execution architecture

The previous Refoundation baseline had useful primitives — canonical tool arguments, budgets, decision receipts, an isolated Git worktree, core receipts, and a session controller — but its execution semantics were still too shallow for a system that must remain trustworthy while other cognition domains evolve independently.

The central architectural problem was not “missing more tools”. It was the lack of a hard transactional boundary between **deciding what should happen** and **making effects happen**.

E. Acting therefore owns only the following question:

> Given an already-selected and already-authorized execution intent, can Nolane perform it within explicit capability, lease, effect, evidence, idempotency, recovery and verification constraints, and can it prove what happened?

E. Acting does **not** own candidate synthesis, planning, goal choice, policy optimization, causal reasoning, or architecture selection. Those remain upstream responsibilities. This prevents E from becoming a second hidden reasoning system and prevents ownership conflicts with the agents upgrading A/B/C/D and other domains.

## 2. Nolane World concepts transferred into Nolane AI

This architecture deliberately transfers mechanisms, not filenames, from Nolane World 0.12.0:

- QX action lifecycle: explicit phases, no commit before postcondition verification.
- R0–R4 execution risk: risk is supplied by an upstream authority; E enforces stronger execution proof requirements for higher risk.
- Evidence-bearing authorization: execution consumes an authorization reference rather than inferring permission from intent.
- Leases: effectful forward progress requires a live, revocable, bounded lease.
- Capability certificates/grants: an action cannot execute if required capabilities are absent.
- Transaction boundary: validate before publish/commit.
- Recovery: executed-but-uncommitted actions can roll back or enter degraded recovery; they cannot silently become success.
- Operational budgets: attempts and side effects are bounded before the effect occurs.
- Durable receipts: lifecycle changes form a deterministic evidence history.

The implementation intentionally strengthens some semantics for Nolane AI. For example, R2/R3/R4 postcondition verification rises through V2/V3/V4 instead of treating all mid-risk actions alike.

## 3. Canonical E. Acting decomposition

```text
AUTHORIZED EXECUTION INTENT
        |
        v
+---------------------------+
|  Invokable Core Contract  |
| schema/capability/effects |
| retry/idempotency/recovery|
+-------------+-------------+
              |
              v
+---------------------------+
|  Acting Protocol Ledger   |  <-- Execution Control
| propose                   |
| lease + capability gate   |
| precondition gate         |
| effect budget gate        |
| execute phase             |
| outcome observation       |
| postcondition gate        |
| commit/rollback/degraded  |
| hash-chained receipts     |
+-------------+-------------+
              |
              v
+---------------------------+
| Transactional Core Kernel |  <-- Executor
| checkpoint (local effect) |
| invoke concrete core      |
| restore or commit         |
| idempotent replay guard   |
+-------------+-------------+
              |
              v
+---------------------------+
| Repository Workspace      |  <-- Execution Workspace
| isolated Git worktree     |
| reversible checkpoints    |
| digest verification       |
+---------------------------+
```

## 4. Boundary contracts with the rest of Nolane AI

### Inputs E may consume

E may consume artifacts that upstream domains have already produced:

- selected tool/core and operation;
- canonical input digest;
- authorization reference;
- risk class;
- capability grants;
- declared preconditions/postconditions;
- precondition/postcondition evidence;
- mutation/effect scope;
- idempotency key;
- recovery plan;
- resource/effect budget.

### Decisions E may make

E may make only execution-safety decisions:

- lease valid/expired/revoked;
- required capability present/absent;
- precondition evidence present/absent;
- effect/attempt budget available/exhausted;
- core invocation succeeded/failed;
- postcondition verifier level sufficient/insufficient;
- local rollback verified/unverified;
- action can commit, must roll back, or must degrade.

### Decisions E must not make

E must not:

- invent a new goal;
- rank candidate plans;
- decide which architecture is preferable;
- reinterpret an unauthorized request into an authorized one;
- raise its own capabilities;
- expand mutation scope;
- convert failure/degraded state into success;
- reuse an idempotency key for semantically different work.

## 5. Execution lifecycle

The canonical lifecycle is:

```text
PROPOSED
   |
   | upstream authorization + capabilities + bounded TTL
   v
LEASED
   |
   | material precondition evidence
   v
PRECONDITION_VERIFIED
   |
   | attempt/effect budget reserved
   v
EXECUTING
   |
   | concrete core receipt / observed exception
   v
OUTCOME_OBSERVED
   |                      \
   | success               \ failure or verifier failure
   v                        v
POSTCONDITION_VERIFIED   ROLLED_BACK (local/read)
   |                        or
   | live lease             DEGRADED (external/irreversible/unverified recovery)
   v
COMMITTED
```

A pre-effect action may also become `CANCELLED`.

### Commit invariant

`COMMITTED` is reachable only from `POSTCONDITION_VERIFIED` while the execution lease is still valid.

A successful tool return is **not** a successful action. It is only an observed outcome that still requires postcondition verification.

### Recovery invariant

Recovery is intentionally allowed even after the forward lease expires. Otherwise lease expiry could trap the runtime after an effect has already happened.

## 6. Risk and verifier semantics

Risk classification is upstream-supplied. E does not calculate strategic risk; it enforces execution proof strength.

| Risk | Minimum postcondition verifier |
|---|---|
| R0 | V1 |
| R1 | V1 |
| R2 | V2 |
| R3 | V3 |
| R4 | V4 |

R4 and irreversible effects require an explicit recovery plan before the contract is admitted.

This does not claim that every R4 action is reversible. It means irreversibility must be explicit and the runtime must not pretend a recovery path exists when it does not.

## 7. Capability and lease model

An `ExecutionContract` declares required capabilities. `acquire_lease()` receives the actual capability grants and refuses to proceed when the required set is not a subset of the grant set.

The execution lease contains:

- action id;
- owner id;
- generation;
- issued timestamp;
- expiry timestamp;
- revocation state;
- deterministic lease id.

Forward transitions verify the lease. Observation and recovery remain possible after expiry.

Lease renewal creates a new generation and a receipt; it does not mutate history invisibly.

## 8. Effect budget model

Per-action budgets complement the existing session budgets in `execution_types.py`.

The action budget currently bounds:

- attempts;
- local mutations;
- external effects.

The kernel reserves the budget before the concrete effect. A budget-exhausted action never reaches the core.

This is intentionally separate from compute/token budgets. Compute budgets constrain thinking/execution cost; effect budgets constrain environmental impact.

## 9. Idempotency semantics

Every action has an explicit caller-provided idempotency key.

The protocol stores a semantic digest over:

- core;
- operation;
- canonical input digest;
- risk/effect class;
- capabilities;
- conditions;
- recovery plan;
- effect budget.

Reusing a key for the same semantic action returns the existing action record. Reusing it for a different semantic action raises `IdempotencyConflict`.

A committed replay never invokes the concrete core again. This directly prevents duplicate side effects caused by retries, reconnects, process recovery, or repeated orchestration messages.

A terminal failed/degraded/cancelled action also does not silently re-execute under the same key. A deliberate retry requires a new idempotency key or a future explicit resume protocol.

## 10. Transaction semantics by effect class

### READ

No workspace mutation checkpoint is required. Failure records a no-side-effect rollback boundary.

### LOCAL_MUTATION

Immediately before concrete execution, the runtime owns a reversible workspace checkpoint. On failure or failed postcondition verification:

1. restore the snapshot;
2. recompute the entire workspace digest;
3. compare it to the checkpoint digest;
4. only then record `ROLLED_BACK`.

If restoration cannot be proven, the action becomes `DEGRADED`, never rolled back by assertion alone.

### EXTERNAL_MUTATION

A local worktree snapshot cannot prove reversal of a remote effect. Therefore failures become `DEGRADED` unless a future core-specific compensation adapter supplies evidence-backed compensation.

### IRREVERSIBLE

The action requires an explicit recovery plan and strong verification. Failure cannot be represented as a clean rollback unless a domain-specific mechanism proves that result.

## 11. Workspace checkpoint semantics

`RepositoryWorkspace` now supports ephemeral checkpoints bound to exactly one isolated worktree.

A checkpoint records:

- checkpoint id;
- workspace root identity;
- before digest;
- label;
- private snapshot directory.

The snapshot excludes Git administrative metadata but captures tracked and untracked worktree payloads, including symlinks. Restore refuses foreign-workspace checkpoints and verifies the resulting digest.

Checkpoints are automatically deleted when the workspace closes.

The checkpoint itself is not the durable evidence store. Durable proof belongs to protocol/core/artifact receipts; the snapshot is only the local undo mechanism.

## 12. Receipt-chain model

Every lifecycle event is canonicalized into an `ExecutionEvent` containing:

- action id;
- sequence;
- resulting phase;
- event type;
- evidence references;
- previous event digest;
- payload digest;
- event digest and receipt id.

For each action, receipts form a hash chain. `from_state()` validates event digests, ids, sequence, previous-digest linkage, ownership, phase/head agreement, and rejects orphan events.

This is tamper-evident rather than cryptographically signed. Signature/trust-root integration is a separate authority concern and must not be invented inside E.

## 13. Invokable Core contract upgrade

`ExternalCoreSpec` is upgraded from descriptive metadata to an execution-facing contract profile. In addition to existing schemas, capabilities, side effects, permissions, failure modes and verification hooks, it now declares:

- supported effect classes;
- idempotency mode;
- retry mode;
- compensation mode;
- maximum attempts;
- deterministic contract digest.

This allows a future registry/certificate authority to bind a core implementation to a stable execution profile without changing the transactional protocol.

## 14. Relationship to the legacy `OrganizationExecutionControlPlane`

The existing `nolane/external_core/execution.py` remains a compatibility path in this pass. It currently combines:

- context compilation;
- neural backend decision-making;
- action-schema checking;
- tool invocation;
- session accounting;
- terminal task state.

That fusion is exactly what the new E boundary is designed to untangle.

The migration direction is:

```text
legacy execution.py
  neural decision + acting
            |
            v
future adapter
  decision receipt -> authorized execution intent
            |
            v
canonical E transactional runtime
```

We deliberately do not rewrite candidate synthesis/context/neural ownership inside the E branch because other specialist agents are upgrading those domains concurrently.

## 15. Failure semantics

| Failure point | Required result |
|---|---|
| invalid capability grant | reject before lease/effect |
| expired/revoked lease | reject forward progress |
| precondition evidence missing | reject before effect |
| effect budget exhausted | reject before core invocation |
| core local mutation fails | restore checkpoint, prove digest, `ROLLED_BACK` |
| local postcondition verification fails | restore checkpoint, prove digest, `ROLLED_BACK`, propagate verification failure |
| external effect fails | `DEGRADED` with recovery evidence |
| rollback cannot be proven | `DEGRADED`, never false rollback |
| commit attempted before postconditions | protocol violation |
| idempotency key reused for different work | conflict |
| persisted receipt tampered | state load fails |

## 16. Non-negotiable invariants

1. No effectful forward progress without a live lease.
2. No capability escalation inside E.
3. No local mutation without an explicit effect budget reservation.
4. No commit without observed outcome and postcondition verification.
5. No false rollback: restoration must match the checkpoint digest.
6. No external/irreversible failure disguised as local rollback.
7. No second invocation for a committed idempotency key.
8. No lifecycle history rewrite; events append and hash-chain.
9. No orphan receipt accepted on state restore.
10. No strategic/candidate-selection logic inside E.

## 17. Verification strategy

The dedicated Refoundation E workflow runs on Python 3.11 and 3.13 and performs:

- compile of canonical external-core modules;
- protocol contract tests;
- workspace rollback tests;
- transactional executor integration tests through the Refoundation wildcard suite;
- full `tests/test_refoundation_*.py` regression gate.

The implementation was developed test-first: the workflow and failing contracts were committed before the new protocol/runtime modules.

## 18. Next integration seam

After other domain upgrades settle, the safe integration task is narrowly defined:

1. introduce an adapter from the upstream authorized decision artifact into `ExecutionContract`/transactional invocation parameters;
2. route existing concrete `ExternalCoreExecutor` calls through `TransactionalExternalCoreExecutor`;
3. preserve old execution/session state import as a compatibility migration;
4. keep reasoning/planning selection outside E;
5. add core-specific compensation adapters for external effects;
6. add durable execution lease persistence when the system gains a shared runtime authority.

That integration can occur without redesigning E again because the transactional boundary is now explicit.
