# D. Goal / Design — Monotonic Decision Lifecycle Authority

## Purpose

This hardening closes an authority-state weakness in `DecisionAuthorityIndex` without changing ownership boundaries in D. Goal / Design. Decision receipts remain immutable; the lifecycle index remains the mutable authority over whether a receipt is currently usable.

The critical invariant is monotonicity: once authority has moved forward into a terminal state, later drift, replay, restore, or competing lifecycle operations must not rewrite history into a weaker state.

## Canonical state machine

```text
ACTIVE
  ├── authority drift / dependency impact ──► STALE
  ├── explicit replacement                ──► SUPERSEDED
  └── explicit withdrawal                 ──► REVOKED

STALE
  ├── explicit replacement                ──► SUPERSEDED
  └── explicit withdrawal                 ──► REVOKED

SUPERSEDED ── terminal
REVOKED    ── terminal
```

There is deliberately no transition from `SUPERSEDED` or `REVOKED` back to `STALE`, and no terminal-to-terminal rewrite. Terminal states describe authoritative historical facts, not transient observations.

## Invariants

1. **Terminal means terminal.** `SUPERSEDED` and `REVOKED` cannot be mutated by `mark_stale()`, `revoke()`, or `supersede()`.
2. **Staleness carries a cause.** `mark_stale()` requires at least one non-empty authority reason. A bare state flip without causal evidence is rejected.
3. **Stale can still close forward.** A `STALE` decision may later be explicitly `REVOKED` or `SUPERSEDED`; this is monotonic closure, not reactivation.
4. **Replacement authority must be live.** A decision may be superseded only by a replacement whose lifecycle is currently `ACTIVE`.
5. **No self-supersession.** A receipt cannot supersede itself.
6. **Supersession is a DAG.** Persisted replacement links must be acyclic. Restore rejects corrupted cyclic authority state rather than accepting it as history.
7. **Historical chains remain valid.** `A → B → C` is valid: A was superseded by B, then B was superseded by C. The graph is historical lineage; it must remain acyclic, not necessarily single-hop-to-active after later evolution.
8. **Persistence fails closed.** Unknown replacement targets, `superseded_by` on non-superseded records, duplicate receipt identities, snapshot disagreement, and supersession cycles are rejected during restore.

## Why this matters

Before this hardening, an already revoked or superseded decision could be rewritten into `STALE`, and a replacement relation could be manipulated into a cycle. That creates authority ambiguity: downstream systems could no longer tell whether a terminal withdrawal/replacement was final, and corrupted persisted state could fabricate circular lineage.

The hardened state machine makes lifecycle progression append-like in semantics even though the index is mutable in storage. Terminal facts cannot be weakened by later calls, while valid forward closure from `ACTIVE` or `STALE` is preserved.

## RED → GREEN evidence

### RED

Test-only head `bdb2c8fc119e02c1bfdf730db1138b58252f0273` ran the existing Goal Design suite plus the new lifecycle invariants. Run `33320123873` failed exactly on the six missing protections while 49 existing/newly-compatible tests remained green:

- terminal revoked decision rewrite was accepted;
- terminal superseded decision rewrite was accepted;
- runtime supersession cycle was accepted;
- persisted supersession cycle was accepted;
- staleness without any reason was accepted;
- a non-active replacement was accepted.

Result on Python 3.11: **6 failed / 49 passed**. Python 3.12 failed on the same hardening gate.

### GREEN

Production head `c456e252422ff3ae75cf72bb57a14b2b92f49367` implements the minimal lifecycle enforcement in `DecisionAuthorityIndex` and bumps `goal_design_runtime` to `0.3.2`.

Run `33320209871` passed the complete Goal Design suite:

- Python 3.11: **55/55 passed**;
- Python 3.12: **55/55 passed**.

## Scope

This wave intentionally does not change GoalSpec evaluation, Pareto authority, five-plane snapshots, traceability, integration guards, context binding, or specialist ownership. It hardens only lifecycle authority and persistence invariants around already-admitted Goal/Design decisions.
