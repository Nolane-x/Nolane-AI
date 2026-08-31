# A9 Temporal Truth — Relation-Aware Temporal v4 Design

Status: **implementation candidate for External Core family A; not accepted until integrated full Refoundation + expected-head merge + post-merge proof.**

## 1. Purpose

A8 made Truth closure dependency-local. A10 then made that dependency scope relation-aware through canonical `RelationSemanticsRegistry` and binding mode `relation-aware-scope-v3`.

The remaining gap is temporal applicability. Without an explicit truth horizon:

- expired evidence can remain usable indefinitely;
- sequential historical states can look simultaneously contradictory;
- verification can be replayed under a different evaluation time;
- closure can remain apparently valid after a relevant validity rule changes.

A9 closes only this gap. It does not create a clock, scheduler, causal-time engine, sixth Truth authority, or replacement for A10.

## 2. Authority model

Family A remains exactly five canonical authorities:

1. `external.evidence`
2. `external.knowledge`
3. `external.epistemic`
4. `external.verification`
5. `external.assurance`

A9 consists of authority-bound sidecars:

- `temporal_truth.py` — deterministic temporal value primitives;
- `evidence_temporal_truth.py` — Evidence-owned validity lineage;
- `knowledge_temporal_truth.py` — Knowledge-owned applicability lineage;
- `epistemic_temporal_truth.py` — Epistemic relation-aware temporal scope;
- `verification_temporal_truth.py` — Verification temporal receipts;
- `assurance_temporal_truth.py` — Assurance temporal closure.

None may declare `COMPONENT_ID`. Existing A1–A10 canonical parents keep authority.

The A6 five-parent subprotocol metadata registry remains unchanged: A9 sidecars are layered protocol refinements under those already-bound parent Truth protocols, not six new canonical components.

## 3. Version ordering

A9 was designed before A10, but A10 was accepted first and already owns:

```text
relation-aware-scope-v3
```

Therefore A9 MUST NOT introduce a parallel temporal v3. Its canonical binding generation is:

```text
relation-aware-temporal-v4
```

The protocol order is exact and non-interchangeable:

```text
global-v1
  ↓
dependency-scope-v2
  ↓
relation-aware-scope-v3
  ↓
relation-aware-temporal-v4
```

A v1/v2/v3 receipt or certificate cannot satisfy v4. V4 cannot be interpreted as any legacy generation.

## 4. Explicit-time determinism

Canonical A9 state never reads wall time. `datetime.now()`, `time.time()`, local timezone defaults and implicit "current time" are forbidden in canonical derivation.

Every temporal operation receives explicit caller input:

```text
explicit as_of
    ↓
TemporalContext
    ↓
Evidence + Knowledge temporal applicability
    ↓
A10 relation-aware competitor selection
    ↓
Temporal Epistemic scope v4
    ↓
Temporal Verification v4
    ↓
Temporal Assurance v4
```

Same canonical repository state + same sidecar histories + same `as_of` must produce the same scope and closure identities.

## 5. Canonical timestamp

Only UTC RFC3339 second precision is accepted:

```text
YYYY-MM-DDTHH:MM:SSZ
```

The parser fails closed on:

- timezone-less values;
- numeric offsets such as `+00:00`;
- fractional seconds;
- surrounding whitespace;
- non-zero-padded fields;
- invalid dates/times;
- alternate spellings of the same instant.

Input is validated, not silently normalized.

## 6. Half-open validity intervals

`TruthInterval` is:

```text
[valid_from, valid_until)
```

Rules:

- lower bound inclusive;
- upper bound exclusive;
- either bound may be open;
- both open means unbounded applicability for that A9 sidecar revision;
- if both exist, `valid_from < valid_until`;
- at `valid_until` the row is already expired.

This permits adjacent state epochs without overlap.

## 7. TemporalContext

`TemporalContext` is immutable and content-addressed. It binds:

- protocol identity;
- exact canonical `as_of`;
- canonical digest.

There is no default context. Receipts and certificates bind both `TemporalContext.digest` and canonical `as_of`.

## 8. Evidence temporal lineage

`EvidenceTemporalBinding` does not mutate `TruthEvidence`. It binds the exact `TruthEvidence.content_digest` to one validity interval and now uses append-only revisions:

- first revision exactly `1` with no predecessor;
- every later revision increments exactly by one;
- every later revision binds `previous_digest` to the exact prior revision;
- same revision semantic rebinding fails closed;
- a lineage cannot switch to a different base evidence digest;
- restore rejects duplicate identities, sequence gaps and predecessor mismatch.

`TemporalEvidenceView.binding(evidence_id)` resolves the latest revision while `revisions(evidence_id)` preserves history.

At explicit `as_of`, state is one of:

- `missing`
- `revoked`
- `binding_mismatch`
- `not_yet_valid`
- `expired`
- `active`

Revocation dominates temporal applicability. An unbound legacy evidence row remains timeless/active unless revoked.

Only current binding state for relevant evidence enters a v4 projection. Because every current digest commits its predecessor, the projection transitively commits the whole revision history without serializing unrelated histories.

## 9. Knowledge temporal lineage

`KnowledgeTemporalBinding` mirrors Evidence rules but binds the exact `KnowledgeClaim.content_digest`.

`TemporalKnowledgeView` preserves append-only revisions and resolves latest applicability. An unbound legacy claim remains timeless.

Required lineage is never erased for convenience: a non-applicable parent remains visible in the scope for audit and causes its descendant to fail closed with `parent_not_applicable` rather than being silently ignored.

## 10. Relation-aware temporal fixed point

A9 inherits A10 relation semantics rather than replacing them.

Starting from the target and all required ancestors:

1. only temporally `active` claims may generate live competitors;
2. `MULTI_VALUED` relations do not add distinct-object siblings merely because values differ;
3. `EXCLUSIVE` relations add applicable sibling objects as competitors;
4. `UNSPECIFIED` relations keep applicable competing values visible so Epistemic can issue ambiguity debt;
5. every admitted competitor contributes its complete parent lineage for audit;
6. non-applicable historical siblings do not fabricate current contradiction.

The fixed point is deterministic and set-canonical.

## 11. Temporal Epistemic scope v4

`TemporalTruthRelationAwareScope` binds all relevant live authority projections:

- target claim ID;
- target lineage IDs;
- relation-aware temporal fixed-point claim IDs;
- referenced evidence IDs;
- relevant relation IDs;
- base scoped Knowledge digest;
- base scoped Evidence digest;
- A10 relevant Relation Semantics projection digest;
- scoped Knowledge temporal projection digest;
- scoped Evidence temporal projection digest;
- exact TemporalContext digest and `as_of`;
- Epistemic assessments;
- relation-authorized contradictions;
- Epistemic/temporal/relation ambiguity debts;
- final canonical scope digest.

`TemporalEpistemicJudge.validate_relation_aware_scope()` never trusts serialized scope as authority. It re-derives it from live canonical Knowledge, Evidence, Relation Semantics, temporal sidecars and explicit context.

## 12. Temporal assessment law

A claim cannot be `SUPPORTED` when:

- the claim itself is not applicable;
- any required parent is not applicable;
- any required parent is not supported;
- cited evidence is missing/revoked/not-yet-valid/expired;
- temporal binding mismatches base content identity;
- evidence subject binding does not equal the claim;
- active support and refutation contradict each other.

Temporal causes become explicit Epistemic debt such as:

- `claim_not_yet_valid`
- `claim_expired`
- `parent_not_applicable`
- `evidence_not_yet_valid`
- `evidence_expired`
- `evidence_revoked`
- `evidence_binding_mismatch`
- `evidence_subject_mismatch`

A10 relation laws still apply to the temporally active supported rows:

- `EXCLUSIVE` → contradiction;
- `MULTI_VALUED` → coexistence;
- `UNSPECIFIED` → relation ambiguity debt.

## 13. Verification v4

A9 uses the separate `TemporalTruthVerificationReceipt` and `TemporalTruthVerificationLedger` rather than widening the A1–A10 receipt type.

Binding mode is exactly:

```text
relation-aware-temporal-v4
```

A receipt binds:

- claim ID;
- verifier identity;
- source family;
- verification channel;
- pass/fail result;
- exact temporal scope digest;
- exact temporal context digest;
- exact canonical `as_of`;
- evidence IDs;
- content digest.

A receipt is current only if claim, scope, context digest and `as_of` all match exactly.

Live provenance additionally requires every verification evidence row to be temporally active and to match claim, verifier, source family and channel. Negative results remain retained. Source mirrors sharing one family count once.

## 14. Assurance v4

`TemporalTruthClosureCertificate` is a dedicated v4 decision receipt. It binds:

- claim and risk;
- exact temporal scope digest;
- exact temporal verification projection digest;
- TemporalContext digest and `as_of`;
- accepted passing receipt IDs;
- Epistemic debt IDs;
- closure decision and reasons;
- content digest.

`TemporalTruthAssuranceGate` uses the same family-A risk thresholds:

- LOW/STANDARD: 1 independent family + 1 channel;
- HIGH: 2 + 2;
- CRITICAL: 3 + 3.

Closure fails on unsupported target, target/ancestor conflict, relation ambiguity, unsupported lineage, critical debt, invalid provenance, negative verification or insufficient independent verification diversity.

A certificate is not self-authenticating. `validate_certificate()` recomputes the entire v4 closure against live canonical state and the exact caller-provided context.

## 15. Invalidation scope

A relevant change must stale old v4 authority:

- relevant Evidence revocation;
- relevant Evidence temporal revision;
- relevant Knowledge temporal revision;
- relevant Knowledge/Evidence base state change;
- relevant relation policy revision;
- verification projection change;
- different `as_of`.

An unrelated change outside the dependency/relation/temporal scope must not stale an otherwise identical certificate. This preserves A8/A10 locality.

## 16. Serialization compatibility

A9 is additive and structural:

- `TruthEvidence` A1–A10 state does not gain temporal keys;
- `KnowledgeClaim` A1–A10 state does not gain temporal keys;
- v1/v2/v3 `TruthVerificationReceipt` states remain unchanged;
- v1/v2/v3 `TruthClosureCertificate` states remain unchanged;
- A9 sidecars use their own protocol identities;
- mixed global/v2/v3/v4 fields fail closed;
- forged digest state fails closed;
- serialized duplicate temporal revision identity fails closed.

No accepted legacy digest is rewritten.

## 17. Canonical authority/non-authority boundary

A9 does not advance canonical parent component versions because parent module APIs and write authorities are not modified. It introduces sidecar protocol software under those parents.

The current component revision law remains:

- `external.knowledge = 0.0.2` from accepted A10;
- other A parents keep their accepted revisions;
- temporal helper modules expose no `COMPONENT_ID`.

Repository audit must remain at zero new migration/reference debt.

## 18. Acceptance gates

A9 is accepted only after an exact final candidate integrated with then-current `main` passes:

1. compile of canonical A modules, A1–A10 Truth helpers and all six A9 sidecars on Python 3.11/3.13;
2. every `tests/test_truth_knowledge_*.py`, including temporal semantics, serialization and revision-lineage attacks;
3. repository authority audit with no duplicate authority/new debt;
4. full Refoundation Epoch 0 on Python 3.11/3.13: 67/67 dossiers, repository audit, Refoundation contracts, Truth contracts, zero-loss evidence, organization/campaign/execution regressions and frozen Neural R2.3;
5. PR diff/review gate showing only intended family-A/workflow/docs/tests changes;
6. expected-head merge;
7. post-merge proof that canonical `main` contains the exact tested tree semantics or an ancestry-preserving subsequent merge with unchanged A9 blobs.

## 19. Non-goals

A9 deliberately does not implement:

- a system clock;
- scheduling;
- automatic expiry jobs;
- deletion of expired state;
- event ordering across all Nolane subsystems;
- bitemporal databases;
- causal temporal inference;
- forecasting;
- a new authority.

Its only question is:

> What does canonical family-A Truth justify **as of this explicit time**, under the exact relation semantics and exact validity histories that apply?
