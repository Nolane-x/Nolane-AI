# A9 Temporal Truth — Implementation Plan

**Goal:** extend the accepted A1–A8 family-A Truth baseline with explicit deterministic temporal validity while preserving every legacy authority, API path, state shape, and digest identity.

**Base:** exact `main` A8 merge `64d1ed5ad816e731068f0612db90c5b32288a465`.

**Branch:** `refoundation/truth-knowledge-a9-temporal-validity`.

## Constraints

- Keep exactly five family-A authorities.
- No implicit wall clock.
- No changes to family F or PR #245 surfaces.
- Legacy v1/v2 state must not gain temporal keys.
- TDD RED proof precedes production code.
- Final acceptance requires focused Truth + full Refoundation on the exact final head, Python 3.11 and 3.13.

## Task 1 — RED temporal capability contract

Add `tests/test_truth_knowledge_hardening_wave9_temporal.py` and prove A8 lacks:

- canonical `TemporalContext`;
- temporal `TruthEvidence` validity intervals;
- temporal `KnowledgeClaim` applicability intervals;
- `as_of` dependency-scope evaluation;
- temporal Verification binding;
- temporal Assurance closure/validation.

Expected RED is capability-specific TypeError/AttributeError/assertion failure, while all A1–A8 tests remain GREEN.

## Task 2 — RED compatibility contract

Add `tests/test_truth_knowledge_hardening_wave9_temporal_serialization.py` covering desired v3 state separation and preserving exact legacy shapes.

RED should show temporal v3 is absent, not break v1/v2.

## Task 3 — Canonical temporal helper

Create `nolane/external_core/temporal_truth.py` as a non-authoritative subprotocol helper.

Implement:

- `CanonicalTimestamp` validation or equivalent private validator;
- immutable `TruthInterval`;
- immutable content-addressed `TemporalContext`;
- half-open interval predicate;
- deterministic `to_state` / `from_state` / digest validation;
- no `COMPONENT_ID`;
- no clock calls.

Add the helper to the focused Truth workflow compile/path list so its direct edits trigger the gate.

## Task 4 — Evidence temporal protocol

Extend `evidence_truth.py` without changing legacy `TruthEvidence` v1 serialization.

Preferred bounded design:

- introduce a temporal evidence protocol value/version or explicit temporal factory that serializes validity bounds only in temporal state;
- preserve legacy `TruthEvidence.create(...)` behavior and digest exactly;
- expose deterministic state at `TemporalContext`:
  `missing`, `revoked`, `not_yet_valid`, `expired`, `active`;
- only active temporal evidence participates in temporal assessment.

## Task 5 — Knowledge temporal protocol

Extend `knowledge_truth.py` without changing legacy `KnowledgeClaim` v1 serialization.

Implement temporal claim applicability with half-open intervals and deterministic round-trip validation.

Legacy claims remain timeless in legacy closure. Temporal closure may accept legacy claims as timeless only where compatibility rules explicitly allow it; temporal claims themselves must obey their interval.

## Task 6 — Epistemic temporal dependency scope

Extend `epistemic_truth.py` with a new temporal scope path rather than changing A8's existing `dependency_scope(...)` identity.

Preferred API:

```python
judge.temporal_dependency_scope(
    claim_id,
    *,
    temporal_context=TemporalContext.create(as_of=...),
    knowledge=knowledge,
    evidence=evidence,
)
```

The temporal scope must:

- resolve target + parent lineage at `as_of`;
- fail closed when required temporal lineage is not applicable;
- include only live competitors at `as_of`;
- expand competitor ancestry to fixed point;
- derive evidence state at `as_of`;
- bind `TemporalContext.digest` into scope digest;
- validate against live authority, not merely self-consistent state.

A8 `dependency_scope(...)` remains unchanged.

## Task 7 — Verification temporal v3

Extend `verification_truth.py` with a third mutually exclusive binding mode, conceptually `dependency-scope-temporal-v3`.

A temporal receipt binds:

- `scope_digest`;
- temporal context digest and canonical `as_of`;
- existing evidence/verifier/source/channel/pass fields.

Legacy v1 and A8 v2 `to_state()` must remain exact.

`TruthVerificationLedger` must expose temporal-current receipt selection that rejects receipts from a different temporal context/scope.

## Task 8 — Assurance temporal v3

Extend `assurance_truth.py` with temporal closure and validation APIs, preferably:

```python
gate.close_temporal(..., temporal_context=context)
gate.validate_temporal_certificate(..., temporal_context=context)
```

Temporal certificates must bind temporal context + temporal scope + temporal verification scope and live-recompute authority state at the bound context.

Legacy `close_snapshot`, `close_live`, and `validate_certificate` behavior remains unchanged.

## Task 9 — GREEN focused gate

Run the `Truth Knowledge A Layer` push workflow on the exact GREEN head.

Required on both Python 3.11 and 3.13:

- compile success;
- all `tests/test_truth_knowledge_*.py` success;
- repository authority audit success.

Do not treat PR-skipped copies as GREEN.

## Task 10 — Integrate current main safely

Before PR/final acceptance:

1. re-fetch current `main`;
2. compare with A9 branch;
3. if `main` moved, integrate it without overwriting concurrent subsystem work;
4. prove A9 diff remains family-A-only;
5. rerun focused gate on the exact integrated head.

## Task 11 — Full Refoundation acceptance

Open PR against current `main` and run Refoundation Epoch 0 on exact integrated head.

Required Python 3.11 + 3.13:

- compile accepted namespaces;
- 67 resolved dossiers fresh;
- quarantine audit fresh;
- Refoundation contracts;
- Truth contracts;
- zero-loss evidence;
- organization/campaign/execution regressions;
- frozen Neural R2.3 checks.

## Task 12 — Candidate to accepted

Only after exact integrated head is fully GREEN:

- update `CURRENT/TRUTH_KNOWLEDGE.md` from A1–A8 accepted to A1–A9 accepted;
- document Temporal Truth semantics and compatibility floor;
- create final candidate commit;
- rerun focused + full Refoundation on that exact final head.

## Task 13 — Merge closure

Before merge verify:

- latest `main` is in branch ancestry;
- PR `mergeable:true`;
- exact diff contains only intended A9 family-A files;
- no unresolved review threads;
- focused final-head GREEN 3.11/3.13;
- full Refoundation final-head GREEN 3.11/3.13.

Merge with `expected_head_sha`.

Post-merge prove:

- `main` points to merge commit;
- merge tree equals final tested tree;
- canonical Truth doc states A1–A9 accepted;
- post-merge push workflows reveal no new failure.
