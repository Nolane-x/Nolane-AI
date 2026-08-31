# E. Acting Execution Provenance Closure Design

Date: 2026-08-31
Status: implemented through TDD acceptance candidate
Scope: E. Acting / Canonical Execution Control

## Context

Crash-safe reconciliation made the acting ledger recoverable across runtime interruption, but recovery correctness depends on the persisted control-plane graph being trustworthy. Before this closure, `OrganizationExecutionControlPlane._validate_state()` established pointer existence but not semantic ownership: a session could reference a real decision, step, or terminal receipt whose embedded provenance belonged to a different execution history. Likewise, acting recovery parsed a `session:decision` idempotency key but did not prove that the bound acting contract represented the exact tool action selected by that decision.

This creates a dangerous recovery asymmetry: persistence can be content-valid at each individual record while cross-record provenance is invalid. A restart must not turn such a graph into authority for an effect or terminal state.

Nolane World was used only as an engineering reasoning aid for failure, trust, reversibility, and evidence-boundary analysis. This design introduces no import, runtime dependency, schema dependency, or architectural coupling from Nolane AI to Nolane World.

## Design objective

Turn E persistence from a collection of individually valid receipts into a provenance-closed execution graph.

The accepted graph must prove:

```text
ExecutionSession
  -> AgentDecisionReceipt
     -> exact selected ToolAction
        -> acting ExecutionContract
           -> transactional lifecycle
              -> CoreInvocationReceipt / recovery outcome
  -> ExecutionStepReceipt or ExecutionTerminalReceipt
```

A reference ID is an address, not authority. Authority comes from agreement between the semantic fields on every edge.

## Threat and failure model

The closure is designed to fail closed under:

- stale snapshots where valid receipts from different sessions are combined;
- cross-session receipt substitution;
- cross-agent decision substitution;
- backend/checkpoint drift hidden behind an existing decision ID;
- action-schema or decision-order substitution;
- a syntactically valid `session:decision` idempotency key attached to a different tool effect;
- restart reconciliation attempting to mutate the acting ledger before discovering a provenance conflict;
- replay of already-projected rows.

It does not claim cryptographic authenticity against an attacker who can replace the entire trusted runtime and codebase. Its responsibility is deterministic internal consistency and fail-closed recovery at the E persistence boundary.

## Persisted graph invariants

For every execution session:

1. `step_index` and the decision-step counter must agree with the persisted decision history length.
2. Decision IDs, step IDs, and core receipt IDs may not be duplicated inside the session.
3. A decision receipt may have only one owning session.
4. Every decision must bind to the session agent, backend, checkpoint, action schema digest, and canonical decision position.
5. A step receipt may have only one owning session.
6. Every step must name its owning session, a decision owned by that session, the exact decision step index, and a core receipt recorded by that session when a core receipt exists.
7. A terminal receipt may have only one owning session.
8. Terminal session/agent/task/state/counters/wall-clock/decision-history/step-history/core-history/output-history must reproduce the terminal session snapshot exactly.
9. Any violation rejects restored state before the control plane becomes usable.

These checks are intentionally performed by the control-plane constructor so `from_state()` remains a pure restoration boundary: invalid persisted graphs do not survive construction.

## Acting-to-decision semantic binding

Before reconciliation mutates any acting row, the control plane resolves the owning decision and verifies that it is a TOOL decision whose selected action matches the acting contract on:

- `core_id == tool_action.tool_id`;
- `operation == tool_action.operation`;
- `input_digest == canonical_digest(tool_action.to_state())`.

This check occurs before projected-row handling and before any call to `ActingProtocolLedger.reconcile_interrupted(...)` or terminal-evidence persistence. Therefore a forged or stale acting row cannot be converted into a legitimate-looking terminal receipt merely because its idempotency key contains a real session and decision ID.

## Recovery ordering

Recovery remains two-phase:

1. **Global preflight**: resolve every candidate row; prove ownership, semantic binding, session liveness, uniqueness, and committed-receipt availability.
2. **Projection**: only after the complete candidate set passes preflight may E reconcile non-terminal acting rows or reconstruct committed step receipts.

This preserves the all-or-nothing property introduced by crash reconciliation: one invalid candidate cannot partially mutate valid sessions before failure.

## Compatibility

No persistence schema is added. Existing canonical receipt shapes remain unchanged. The hardening is validation-only plus recovery preflight semantics.

The compatibility-facing execution controller remains in E because upstream C/D surfaces are being refounded independently. This closure does not move planning, candidate selection, strategic authorization, or inference into E.

## Versioning

`external.execution.control` advances from `0.0.4` to `0.0.5` because accepted local semantics change: persisted control state now has stronger admissibility criteria and restart reconciliation gains semantic decision-contract binding.

Other E component versions remain unchanged in this wave.

## TDD evidence contract

The RED suite must demonstrate that the previous implementation:

- accepts a decision receipt bound to the wrong agent;
- accepts a step receipt whose embedded session differs from its owning session;
- accepts a terminal receipt whose embedded session differs from its owning session;
- allows a semantically different acting contract with a valid `session:decision` key to progress into recovery mutation/evidence creation.

GREEN requires those cases to fail closed while existing crash-reconciliation and commit-projection contracts remain green on CPython 3.11 and 3.13, followed by the complete Refoundation suite.

## Non-goals

- No Nolane World runtime integration.
- No new planning or policy logic.
- No resumption of uncertain effects.
- No new persistence schema.
- No distributed consensus protocol.
- No claim that an external side effect is reversible merely because a local workspace is restorable.

## Next hardening frontier

After this closure is canonical, the next E-wide frontier is proof continuity across all four E areas: Invokable Core capability identity, Workspace checkpoint generation/fencing, Executor receipt-to-contract binding, and Execution Control projection. Those should be treated as one execution-proof chain rather than four independent feature modules.
