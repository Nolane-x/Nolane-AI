# A9 Temporal Truth — Design Specification

Status: proposed RED-first Refoundation continuation for External Core family A.

## 1. Problem

A8 made canonical Truth closure dependency-local, but its live state is still timeless. `EvidenceLedger.is_active()` distinguishes present/revoked evidence, while dependency scopes and live certificates do not express *when* a fact or evidence item is applicable.

This creates four semantic hazards:

1. evidence that should have expired can continue supporting a claim indefinitely;
2. two facts that are both valid but belong to disjoint historical periods can be treated as simultaneous competitors;
3. verification receipts can be reused at a different evaluation time without any temporal binding;
4. assurance certificates can remain structurally valid even when the requested truth horizon moves outside the validity interval that justified closure.

A9 closes this gap without creating a sixth family-A authority.

## 2. Authority invariant

Family A remains exactly five canonical authorities:

- Evidence
- Knowledge
- Epistemic
- Verification
- Assurance

A9 is a subprotocol spanning those authorities. A helper module may own deterministic temporal normalization and interval predicates, but it MUST NOT declare `COMPONENT_ID`, own a ledger, or become a peer authority.

## 3. Determinism invariant

A9 MUST NOT call `datetime.now()`, `time.time()`, or any implicit wall clock while deriving canonical state.

Temporal evaluation is always explicit input:

```text
caller supplied as_of
        ↓
canonical TemporalContext
        ↓
Knowledge/Evidence applicability
        ↓
Epistemic dependency scope
        ↓
Verification binding
        ↓
Assurance binding + live revalidation
```

The same repository state plus the same canonical `as_of` MUST produce the same temporal scope digest and closure result.

## 4. Canonical timestamp form

A9 canonical timestamps use UTC RFC3339 second precision:

```text
YYYY-MM-DDTHH:MM:SSZ
```

Examples:

- `2026-08-30T13:00:00Z`
- `2030-01-01T00:00:00Z`

Rejected forms include:

- timezone-less timestamps;
- non-UTC offsets;
- fractional seconds;
- non-zero-padded components;
- impossible calendar values;
- surrounding whitespace;
- alternate textual spellings that normalize to the same instant.

Canonicalization is fail-closed rather than silently rewriting caller input.

## 5. Interval model

Temporal records use half-open validity intervals:

```text
[valid_from, valid_until)
```

Rules:

- `valid_from` is inclusive;
- `valid_until` is exclusive;
- either bound may be absent for an open-ended interval;
- when both are present, `valid_from < valid_until` is required;
- an interval with neither bound is equivalent to timeless applicability only for the new temporal protocol object itself;
- legacy A1–A8 records remain governed by legacy timeless semantics and are not rewritten.

Half-open intervals guarantee adjacent epochs do not overlap accidentally:

```text
old: [2020-01-01, 2025-01-01)
new: [2025-01-01, ∞)
```

At exactly `2025-01-01T00:00:00Z`, only the new fact applies.

## 6. TemporalContext

A9 introduces a content-addressed `TemporalContext` subprotocol value containing at minimum:

- `as_of`
- protocol/version identity
- canonical digest

It is immutable and deterministic. Its digest is bound into A9 scope, verification, and assurance identities.

A temporal closure MUST receive an explicit `TemporalContext` or explicit canonical `as_of` from which one is constructed. No default current time exists.

## 7. Evidence temporal semantics

A9 temporal evidence carries an interval in its new serialization/version while preserving the exact A1–A8 `TruthEvidence` v1 state shape for legacy records.

At an explicit `as_of`, evidence state is one of:

- `missing`
- `revoked`
- `not_yet_valid`
- `expired`
- `active`

Only `active` temporal evidence can support or oppose a temporal assessment.

Revocation remains stronger than temporal applicability: a revoked row is `revoked` regardless of interval.

## 8. Knowledge temporal semantics

A9 temporal claims carry their applicability interval in a new protocol/version. Legacy `KnowledgeClaim` serialization and content digests remain exact.

A temporal claim is eligible for the requested closure only if its interval contains `as_of`.

Parent lineage is fail-closed: if a required temporal parent is not applicable at `as_of`, the descendant cannot be canonically supported through that parent.

## 9. Temporal competition

A8 defines potential competitors by `(subject, relation)` and includes competitor ancestry in the fixed point.

A9 refines this rule for temporal closure:

- only claims applicable at the requested `as_of` may become live competitors;
- a non-applicable historical claim MUST NOT create a present-time contradiction;
- competitor ancestry is still expanded to a fixed point after temporal filtering;
- legacy non-temporal closure retains A8 behavior exactly.

This prevents false contradictions between sequential world states.

## 10. Temporal dependency scope

A9 temporal dependency scope extends A8 scope identity with the temporal context digest and temporal applicability state.

Its canonical identity binds at minimum:

- target claim;
- lineage claims applicable at `as_of`;
- live competitors applicable at `as_of`;
- evidence state at `as_of`;
- contradictions/debts derived at `as_of`;
- `TemporalContext.digest`.

Changing only `as_of` MAY change the scope digest when applicability changes. It MUST NOT rely on wall-clock mutation.

## 11. Verification v3

A9 introduces a temporal verification binding mode/version, conceptually:

```text
dependency-scope-temporal-v3
```

A v3 receipt binds:

- claim ID;
- temporal dependency scope digest;
- temporal context digest / canonical `as_of`;
- evidence IDs;
- existing verifier/source/channel/pass semantics.

A receipt for time T1 MUST NOT satisfy closure for T2 unless the exact canonical temporal scope identity and temporal context binding match the T2 request.

A1–A8 v1 global and v2 dependency-scoped receipt serialization remains byte-for-byte unchanged.

## 12. Assurance v3

A9 temporal assurance produces a v3 certificate bound to:

- claim ID and risk;
- temporal scope digest;
- verification temporal-scope digest;
- temporal context digest / canonical `as_of`;
- accepted receipt IDs;
- debt IDs;
- closure result and reasons.

Live validation MUST recompute the canonical temporal scope at the certificate's bound temporal context and reject:

- interval drift caused by changed underlying records;
- evidence revocation;
- verification mismatch;
- forged temporal state;
- caller attempts to validate the certificate under a different `as_of`.

No implicit revalidation at "now" is allowed.

## 13. Compatibility rules

A9 has a strict compatibility floor:

1. v1 `TruthEvidence` and `KnowledgeClaim` state/digest identity is unchanged.
2. v1 global `TruthVerificationReceipt` state is unchanged.
3. v2 dependency-scoped `TruthVerificationReceipt` state is unchanged.
4. v1 global `TruthClosureCertificate` state is unchanged.
5. v2 dependency-scoped `TruthClosureCertificate` state is unchanged.
6. A8 non-temporal `dependency_scope(...)`, `close_live(...)`, and certificate validation retain current behavior.
7. No legacy state receives new `None`, empty, or default temporal keys.
8. New temporal state cannot be deserialized as a legacy binding mode and vice versa.

## 14. Fail-closed rules

A9 rejects:

- malformed or noncanonical timestamps;
- inverted or zero-width bounded intervals;
- temporal state without explicit temporal protocol identity;
- mixed global/scoped/temporal binding fields;
- temporal receipt or certificate missing its temporal context binding;
- temporal receipt/certificate used with a different `as_of`;
- temporal lineage whose required parent is not applicable;
- forged temporal scope state even if its internal digest was recomputed by the attacker.

## 15. RED proof requirements

Before production implementation, tests must demonstrate that A8 cannot currently satisfy A9 semantics. At minimum RED must prove:

1. temporal evidence validity is unsupported, allowing the expired-evidence hazard;
2. temporal claim applicability is unsupported, allowing historical false competition;
3. verification has no `as_of`/temporal scope binding;
4. assurance has no `as_of`/temporal live revalidation;
5. half-open boundary semantics are absent;
6. canonical malformed timestamp rejection is absent as a family-A protocol.

RED failures must be caused by missing A9 capability, not unrelated regressions.

## 16. GREEN acceptance requirements

Focused Truth gate on Python 3.11 and 3.13 must prove:

- all A1–A8 contracts remain GREEN;
- all A9 temporal contracts are GREEN;
- repository authority audit remains GREEN;
- helpers expose no `COMPONENT_ID`;
- canonical serialization round-trips and forged-state rejection work.

Before merge, full Refoundation Epoch 0 must additionally prove:

- 67/67 AI dossiers fresh;
- repository quarantine audit fresh;
- zero-loss evidence generation;
- organization/campaign/execution regressions;
- frozen Neural R2.3 invariants.

## 17. Non-goals

A9 does not introduce:

- a scheduler;
- a global system clock;
- event-time ordering for all Nolane subsystems;
- causal temporal reasoning;
- prediction/forecast semantics;
- TTL mutation jobs;
- automatic deletion of expired evidence;
- a sixth Truth authority.

It only gives canonical family-A Truth closure an explicit, deterministic answer to the question:

> "True/verified/assured **as of when**?"
