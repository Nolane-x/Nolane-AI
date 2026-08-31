# E. Acting Execution Provenance Closure Implementation Plan

**Goal:** Make restored E execution state and crash reconciliation provenance-closed instead of pointer-valid only.

**Architecture:** Strengthen `OrganizationExecutionControlPlane` at the persistence/recovery boundary. Preserve existing receipt schemas and transactional execution flow; reject cross-record semantic inconsistencies during construction and before recovery mutation.

## Task 1 — Establish RED provenance contracts

Files:
- Create `tests/test_refoundation_acting_control_provenance.py`
- Update `.github/workflows/refoundation-e-acting.yml`

Acceptance:
- wrong-agent decision binding is accepted by old production and therefore RED;
- cross-session step binding is accepted by old production and therefore RED;
- cross-session terminal binding is accepted by old production and therefore RED;
- mismatched acting contract reaches mutation/evidence on old production and therefore RED;
- the dedicated E workflow executes the new test explicitly on Python 3.11 and 3.13.

## Task 2 — Close persisted execution graph provenance

Files:
- Modify `nolane/external_core/execution.py`

Implementation:
- validate decision ownership and execution identity fields;
- validate canonical decision ordering and session counters;
- validate step ownership and decision/core bindings;
- validate terminal ownership and terminal snapshot equivalence;
- reject receipt sharing across sessions;
- keep validation deterministic and effect-free.

Acceptance:
- all persisted-graph RED cases become GREEN;
- `from_state()` performs no effectful recovery or inference.

## Task 3 — Bind acting recovery to the selected tool action

Files:
- Modify `nolane/external_core/execution.py`

Implementation:
- add an effect-free semantic matcher between `AgentDecisionReceipt` and acting contract;
- compare tool/core identity, operation, and canonical input digest;
- execute the check during global recovery preflight before projected-row handling or ledger mutation.

Acceptance:
- mismatched contract fails before `reconcile_interrupted()` and before terminal evidence creation;
- normal committed projection and interrupted-action recovery remain unchanged.

## Task 4 — Version and authority documentation

Files:
- Modify `nolane/metadata/component_versions.py`
- Modify `tests/test_refoundation_component_versions.py`
- Modify `tests/test_refoundation_wave5aa_native_execution_control.py`
- Modify `CURRENT/E_ACTING.md`
- Create `docs/superpowers/specs/2026-08-31-e-acting-execution-provenance-closure-design.md`

Acceptance:
- `external.execution.control` is `0.0.5` everywhere;
- CURRENT records provenance closure as an E invariant;
- Nolane World is described only as a reasoning input, never a runtime dependency.

## Task 5 — Hosted acceptance and cleanup

Acceptance sequence:
1. deterministic production patch apply;
2. compile canonical E modules;
3. targeted provenance + crash-recovery contracts GREEN;
4. remove staging patch/workflow artifacts;
5. clean-head E matrix GREEN on Python 3.11 and 3.13;
6. full `tests/test_refoundation_*.py` GREEN on both interpreters;
7. compare candidate against latest `main` and preserve concurrent specialist work;
8. inspect final diff for scope and accidental artifacts;
9. merge only from the exact tested head;
10. verify actual merge tree and post-merge state.

## Task 6 — Open the next E-wide proof-continuity wave

After provenance closure is canonical, test-drive proof continuity across:

- Invokable Cores: immutable capability/profile identity used by execution;
- Execution Workspace: checkpoint generation/fencing so stale restore authority cannot cross execution epochs;
- Executor: bind core receipts back to the exact invocation contract and workspace generation;
- Execution Control: consume only receipts whose proof chain closes end-to-end.

This task is intentionally deferred until Tasks 1–5 are canonical so the next architecture wave builds on a trusted recovery substrate.
