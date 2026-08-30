# Refoundation E. Acting Transactional Runtime — Implementation Plan

> This plan is execution-oriented and scoped to E. Acting. It deliberately avoids rewriting upstream reasoning, candidate synthesis, planning, architecture, or policy ownership.

**Goal:** Replace shallow effect dispatch semantics with a lease-aware, capability-bounded, idempotent, evidence-gated transactional acting boundary while preserving compatibility with existing concrete core implementations.

**Architecture:** Introduce an append-only acting protocol ledger as execution control, reversible repository checkpoints as the local transaction substrate, an execution-profiled Invokable Core registry, and a transactional wrapper around the existing concrete `ExternalCoreExecutor`. Keep `execution.py` as a compatibility bridge until upstream domain refactors settle.

**Source:** Nolane AI Refoundation contracts + transferred operational mechanisms from Nolane World 0.12.0 QX action lifecycle, leases, capability certification, transaction validation, recovery, and operational controls.

---

## Task 1 — Establish an isolated E branch and dedicated CI gate

**Files**
- Create: `.github/workflows/refoundation-e-acting.yml`

**Actions**
1. Branch from authoritative `main`.
2. Gate Python 3.11 and 3.13.
3. Compile canonical `nolane/external_core` modules.
4. Run E-specific transactional tests.
5. Run all `tests/test_refoundation_*.py` regressions.
6. Preserve JUnit diagnostics on failure.

**Evidence requirement:** workflow must show RED for pre-implementation contracts, then GREEN after implementation.

## Task 2 — Specify execution-control invariants test-first

**Files**
- Create: `tests/test_refoundation_acting_protocol.py`

**Required failing contracts before code exists**
- commit cannot bypass postcondition verification;
- expired lease blocks forward progress;
- recovery remains possible after lease expiry;
- idempotency replay cannot change semantics;
- missing capabilities block execution;
- effect budgets are checked before execution;
- R4 needs recovery plan and V4 verification;
- failed effect can roll back without false commit;
- serialized event-chain tampering is rejected.

## Task 3 — Implement canonical Execution Control

**Files**
- Create: `nolane/external_core/acting_protocol.py`

**Core types**
- `ExecutionRisk` R0–R4;
- `EffectClass`;
- `ActionPhase`;
- `VerifierLevel`;
- `ActionBudget`;
- `ExecutionContract`;
- `ExecutionLease`;
- `ExecutionEvent`;
- `ActionRecord`;
- `ActingProtocolLedger`.

**Transition rules**
1. `PROPOSED -> LEASED` only with authorization evidence and required capabilities.
2. `LEASED -> PRECONDITION_VERIFIED` only with a live lease.
3. `PRECONDITION_VERIFIED -> EXECUTING` only after reserving attempt/effect budget.
4. `EXECUTING -> OUTCOME_OBSERVED` records concrete outcome evidence.
5. successful outcome -> postcondition verification at risk-dependent verifier level.
6. commit only from verified postconditions and live lease.
7. executed failure -> rollback or degraded recovery, never false success.

**Durability rules**
- canonical state representation;
- hash-chained event receipts;
- no orphan events;
- load-time integrity verification;
- semantic idempotency collision detection.

## Task 4 — Specify workspace rollback test-first

**Files**
- Create: `tests/test_refoundation_acting_workspace.py`

**Required contracts**
- restore tracked mutation;
- remove untracked mutation created after checkpoint;
- reproduce exact pre-action workspace digest;
- reject checkpoint from a different worktree;
- clean snapshot directories on workspace close.

## Task 5 — Upgrade Execution Workspace

**Files**
- Modify: `nolane/external_core/execution_workspace.py`

**Implementation**
1. Add `WorkspaceCheckpoint`.
2. Snapshot worktree payload outside the live worktree while excluding Git administrative metadata.
3. Bind checkpoint identity to workspace root + digest + monotonic local counter.
4. Restore all tracked/untracked payload.
5. Recompute and compare the canonical workspace digest.
6. Do not claim rollback if digest proof fails.
7. Remove checkpoints explicitly or during workspace close.

## Task 6 — Upgrade Invokable Core contracts

**Files**
- Modify: `nolane/external_core/invokable.py`

**Add execution profile fields**
- effect classes;
- idempotency mode;
- retry mode;
- compensation mode;
- max attempts;
- contract digest.

**Compatibility constraint:** retain existing constructor/state semantics by adding defaulted fields and tolerant `from_state()` behavior for earlier snapshots.

## Task 7 — Specify transactional Executor test-first

**Files**
- Create: `tests/test_refoundation_acting_runtime.py`

**Required contracts**
- successful local mutation commits only after postcondition verification;
- failed local mutation restores exact bytes/digest then records rollback;
- committed idempotency replay does not invoke the concrete executor twice.

## Task 8 — Implement transactional Executor kernel

**Files**
- Create: `nolane/external_core/acting_runtime.py`

**Flow**
1. Build deterministic action identity from actor/task/idempotency key.
2. Build `ExecutionContract` from canonical `ToolAction` digest plus upstream execution metadata.
3. Reserve idempotency key.
4. Acquire capability-bounded execution lease.
5. Verify preconditions.
6. Reserve effect budget.
7. For local mutation, create workspace checkpoint.
8. Invoke existing concrete core executor.
9. Observe core outcome receipt.
10. On failure: restore+prove rollback for local effects; degrade external/irreversible effects.
11. On success: verify postconditions.
12. Commit only after postconditions pass.
13. Release checkpoint.
14. Replay committed idempotency keys from receipt history instead of reinvoking.

## Task 9 — Document ownership and migration

**Files**
- Create: `docs/superpowers/specs/2026-08-30-refoundation-e-acting-transactional-runtime-design.md`
- Create: `CURRENT/E_ACTING.md`

**Document**
- E ownership boundary;
- upstream/downstream contracts;
- lifecycle and invariants;
- risk/verifier model;
- effect-specific recovery semantics;
- compatibility role of legacy `execution.py`;
- exact next adapter seam after other specialist-agent changes settle.

## Task 10 — Regression, forensic review, and handoff

**Verification**
1. E-specific tests green on Python 3.11 and 3.13.
2. All Refoundation tests green on Python 3.11 and 3.13.
3. Compare branch against current main to detect accidental cross-domain edits.
4. Inspect changed-file patches for scope leakage.
5. Verify no direct candidate-selection or architecture-policy logic entered E.
6. Run code-review checklist.
7. Create a PR rather than silently overwriting concurrent specialist work.

**Completion rule:** do not describe the branch as complete while either matrix leg or the Refoundation regression suite is failing.
