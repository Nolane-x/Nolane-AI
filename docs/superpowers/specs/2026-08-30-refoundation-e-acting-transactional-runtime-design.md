# Refoundation E. Acting — Transactional Runtime Design

**Date:** 2026-08-30  
**Scope owner:** `E. Acting` only  
**Status:** implemented and fail-closed hardened architecture baseline (`0.1.x`)  
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
| elapsed-time lease gate   |
| restore or commit         |
| idempotent replay guard   |
+-------------+-------------+
              |
              v
+---------------------------+
| Repository Workspace      |  <-- Execution Workspace
| isolated Git worktree     |
| reversible checkpoints    |
| full-payload digest proof |
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

Lease validity is evaluated using the caller's canonical `now_ms` as the deterministic acquisition epoch plus monotonic elapsed runtime time. A slow core therefore cannot reuse the acquisition timestamp and commit after its TTL has actually expired.

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

The transactional kernel tracks elapsed runtime with a monotonic clock and advances the protocol timestamp at precondition verification, execution start, outcome observation, postcondition verification, and commit. This closes the stale-clock class of lease bypasses while retaining deterministic caller-supplied acquisition time.

Lease renewal creates a new generation and a receipt; it does not mutate history invisibly.

Protocol `0.1.2` additionally binds **modern** lease identity to the immutable event chain. Acquisition receipts include `lease:<lease_id>` beside authorization evidence; renewal receipts include both `lease:<new_id>` and `previous-lease:<old_id>`; revocation receipts bind the revoked lease id. Restore checks generation count, modern renewal linkage, revocation state, and the final persisted lease against those lifecycle references. Recomputing a local lease id and `ActionRecord` digest is therefore insufficient to rebind a modern persisted lease.

Historical schema-1 events created before this binding existed remain loadable. They retain weaker compatibility semantics because E cannot retroactively manufacture lease evidence that an old event never recorded; compatibility is explicit rather than misrepresented as modern proof strength.

## 8. Effect budget model

Per-action budgets complement the existing session budgets in `execution_types.py`.

The action budget currently bounds:

- attempts;
- local mutations;
- external effects.

The kernel reserves the budget before the concrete effect. A budget-exhausted action never reaches the core.

This is intentionally separate from compute/token budgets. Compute budgets constrain thinking/execution cost; effect budgets constrain environmental impact.

The organization-level `max_external_core_calls` counter remains specific to registered external-core invocations. It is not redefined as a generic external-effect counter merely because unconfined process tools receive external-like transactional semantics.

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

READ is reserved for effects E can conservatively treat as side-effect-free. `terminal`, `compiler`, and `test-runner` do not qualify merely because their repository input is a disposable copy: a repository copy is not an operating-system sandbox and does not confine process/network/host effects. The compatibility adapter therefore classifies these tools as external-like R3/V3 execution.

### LOCAL_MUTATION

Immediately before concrete execution, the runtime owns a reversible workspace checkpoint. On failure or failed postcondition verification:

1. restore the snapshot;
2. recompute the entire workspace digest;
3. compare it to the checkpoint digest;
4. only then record `ROLLED_BACK`.

If restoration cannot be proven, the action becomes `DEGRADED`, never rolled back by assertion alone.

### EXTERNAL_MUTATION

A local worktree snapshot cannot prove reversal of a remote or otherwise unconfined effect. Therefore failures become `DEGRADED` unless a future core-specific compensation adapter supplies evidence-backed compensation.

External classification takes precedence over local mutation hints. If an already-selected tool action is both external and carries local mutation metadata, the compatibility adapter must not downgrade it to `LOCAL_MUTATION` merely because local rollback information exists.

### IRREVERSIBLE

The action requires an explicit recovery plan and strong verification. Failure cannot be represented as a clean rollback unless a domain-specific mechanism proves that result.

## 11. Workspace checkpoint semantics

`RepositoryWorkspace` supports ephemeral checkpoints bound to exactly one isolated worktree.

A checkpoint records:

- checkpoint id;
- workspace root identity;
- before digest;
- label;
- private snapshot directory.

The snapshot excludes Git administrative metadata and captures the complete worktree payload. The rollback digest traverses the same payload authority and includes tracked, untracked and ignored files, file byte hashes and sizes, symlink targets, directory entries, and empty directories. Git status and HEAD remain metadata inputs, but `git ls-files` is not the authority for rollback identity.

Restore refuses foreign-workspace checkpoints and verifies the resulting full-payload digest. A rollback cannot be declared successful when ignored or structurally empty payload has drifted outside the old Git-visible file set.

Checkpoints are automatically deleted when the workspace closes.

The checkpoint itself is not the durable evidence store. Durable proof belongs to protocol/core/artifact receipts; the snapshot is only the local undo mechanism.

## 12. Receipt-chain and persisted-state model

Every lifecycle event is canonicalized into an `ExecutionEvent` containing:

- action id;
- sequence;
- resulting phase;
- event type;
- evidence references;
- previous event digest;
- payload digest;
- event digest and receipt id.

For each action, receipts form a hash chain. `from_state()` validates event digests, ids, sequence, previous-digest linkage, ownership, phase/head agreement, and rejects orphan events. Persisted modern `ActionRecord` snapshots are independently content-addressed and cross-checked against immutable lifecycle events: the proposed contract, authorization, pre/postcondition evidence, execution counters, outcome, verifier state, terminal references, and modern lease bindings cannot be rebound merely by recomputing local state digests.

Schema version remains `1` for backward compatibility. Records written before local `ActionRecord.digest` existed may therefore omit that field. Such a record is not trusted because it lacks the field: it is accepted only if the event chain and complete record projection validate. The next `to_state()` deterministically enriches it with the content digest. If a digest is present, it must match exactly.

Modern lease transitions have stronger lifecycle evidence than historical schema-1 transitions. The restore path explicitly distinguishes those cases and does not claim that legacy receipts provide evidence they never stored.

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
canonical compatibility adapter
  decision receipt -> authorized execution intent
            |
            v
canonical E transactional runtime
```

We deliberately do not rewrite candidate synthesis/context/neural ownership inside the E branch because other specialist agents are upgrading those domains concurrently.

The adapter uses a fail-closed compatibility classification order: registered external cores and unconfined process tools first, local workspace mutation second, genuinely read-only operations last. `terminal`, `compiler`, and `test-runner` receive external-like `EXTERNAL_MUTATION` / R3 / V3 semantics because their host-level effects are not proven reversible by the disposable repository copy.

## 15. Failure semantics

| Failure point | Required result |
|---|---|
| invalid capability grant | reject before lease/effect |
| expired/revoked lease before core | reject forward progress |
| lease expires while core is running | observe/recover as required; never commit using the stale acquisition timestamp |
| precondition evidence missing | reject before effect |
| effect budget exhausted | reject before core invocation |
| core local mutation fails | restore checkpoint, prove full-payload digest, `ROLLED_BACK` |
| local postcondition verification fails | restore checkpoint, prove full-payload digest, `ROLLED_BACK`, propagate verification failure |
| external effect fails | `DEGRADED` with recovery evidence |
| unconfined process effect fails | `DEGRADED`; never a synthetic no-side-effect READ rollback |
| external action also carries local mutation hints | external semantics dominate; never downgrade to local rollback semantics |
| rollback cannot be proven | `DEGRADED`, never false rollback |
| commit attempted before postconditions | protocol violation |
| idempotency key reused for different work | conflict |
| supplied persisted record digest tampered | state load fails |
| modern persisted lease identity/revocation/generation diverges from lifecycle evidence | state load fails |
| legacy schema-1 record omits local digest but lifecycle projection is invalid | state load fails |

## 16. Non-negotiable invariants

1. No effectful forward progress without a live lease.
2. No capability escalation inside E.
3. No local mutation without an explicit effect budget reservation.
4. No commit without observed outcome and postcondition verification.
5. No false rollback: restoration must match the full-payload checkpoint digest.
6. No external/irreversible failure disguised as local rollback.
7. No second invocation for a committed idempotency key.
8. No lifecycle history rewrite; events append and hash-chain.
9. No orphan receipt accepted on state restore.
10. No strategic/candidate-selection logic inside E.
11. No stale-clock lease bypass: elapsed core runtime participates in every post-acquisition forward lease check.
12. No Git-visibility proof gap: ignored files and empty directories participate in workspace identity and rollback proof.
13. No local-hint downgrade: external effect classification precedes local mutation rollback metadata.
14. No process-as-read fiction: unconfined process tools require at least the external-like R3/V3 compatibility floor unless a future stronger sandbox proves a narrower effect class.
15. No local-digest rebinding: modern record/lease state must agree with immutable lifecycle projections even if an attacker recomputes local content identifiers.
16. No false migration claim: legacy schema-1 records may be enriched on write only after their available lifecycle evidence validates; missing historical lease-binding evidence is treated as compatibility debt, not retroactive proof.

## 17. Verification strategy

The dedicated Refoundation E workflow runs on Python 3.11 and 3.13 and performs:

- compile of canonical external-core modules;
- protocol contract tests;
- persisted-record and lifecycle-bound lease integrity tests;
- schema-1 digest-less restore/enrichment regression tests;
- workspace rollback tests;
- transactional executor integration tests through the Refoundation wildcard suite;
- elapsed-time lease-expiry regression tests;
- ignored-file and empty-directory workspace identity regressions;
- external-over-local effect-precedence regression tests;
- unconfined process-tool R3/V3 regression tests;
- full `tests/test_refoundation_*.py` regression gate.

The implementation was developed test-first. Each late forensic hardening issue was first reproduced as a failing contract and only then moved to GREEN implementation.

## 18. Canonical integration seam — implemented

The compatibility integration is closed on this branch:

1. the already-issued `AgentDecisionReceipt` is bound to the E execution contract as upstream authorization evidence;
2. canonical TOOL execution routes through `TransactionalExternalCoreExecutor`, never directly through `ExternalCoreExecutor.invoke`;
3. legacy execution/session state remains loadable while transactional ledger state is persisted and restored alongside it;
4. task/identity authority state is bound into precondition evidence and existing identity permissions/bindings supply the capability grants;
5. risk classes are paired with their minimum verifier levels before any effect can start;
6. successful concrete-core receipts contribute their persisted evidence artifact to postcondition verification;
7. reasoning/planning selection remains outside E;
8. elapsed lease time is enforced through the transactional kernel rather than frozen at invocation entry;
9. local rollback proof is byte/structure-complete for the worktree payload outside Git administrative metadata;
10. external effects cannot be downgraded by local mutation hints; and
11. unconfined process tools are conservatively bound to external-like R3/V3 semantics.

Core-specific compensation beyond the generic degraded/recovery contract remains an owner-core extension point rather than a reason to bypass E.

## 19. Hardened semantic component revisions

The forensic hardening advances only components whose execution semantics changed:

| Component | Hardened version | Reason |
|---|---:|---|
| `external.execution.workspace` | `0.0.3` | full-payload rollback identity and proof |
| `external.acting.protocol` | `0.1.2` | legacy digest-less record enrichment plus lifecycle-bound modern lease identity/revocation integrity |
| `external.acting.runtime` | `0.1.1` | monotonic elapsed-time lease enforcement |
| `external.execution.control` | `0.0.3` | fail-closed external precedence and process-tool R3/V3 mapping |

These version changes do not alter canonical first-generation runtime state. The accepted E runtime-state fingerprint therefore remains `eda96a54b833dee2a3eb2a3e697fb658f4ff73729fff76fa6746ba554a6d602e` rather than creating a false new persistence cutover. Protocol `0.1.2` preserves schema version 1 and changes validation/enrichment semantics rather than the empty canonical first-generation ledger shape.
