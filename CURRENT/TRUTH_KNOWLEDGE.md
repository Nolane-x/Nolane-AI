# Truth / Knowledge — External Core A

Status: **A1–A10 are accepted as the canonical External Core family-A Truth / Knowledge baseline. A9 Temporal Validity is accepted as relation-aware temporal v4 on top of A10 relation-aware scope v3.**

## Canonical authority model

External Core family A remains exactly five canonical component authorities:

1. `external.evidence` → `nolane.external_core.evidence`
2. `external.knowledge` → `nolane.memory.knowledge`
3. `external.epistemic` → `nolane.external_core.epistemic`
4. `external.verification` → `nolane.external_core.verification`
5. `external.assurance` → `nolane.external_core.assurance`

Truth Closure is additive protocol semantics beneath those authorities. No Truth or Temporal helper may declare `COMPONENT_ID`.

All canonical Truth identity uses `nolane.core.canonical_digest.canonical_digest`.

## Accepted A1–A7 baseline

The accepted baseline provides:

- immutable provenance-aware Evidence with source identity/family binding, polarity, channels, append-only revocation, anti-rebinding, anti-cross-subject laundering and tamper-evident restore;
- content-addressed Knowledge propositions with evidence references, derivation DAGs, topological restore, transitive invalidation and canonical set ordering;
- first-class Epistemic `UNKNOWN`, `SUPPORTED`, `REFUTED`, `CONTRADICTED`, competing propositions and epistemic debt;
- exact-state Verification receipts, live provenance validation, source-family independence, channel diversity and retained negative results;
- risk-sensitive Assurance, live canonical recomputation and non-self-authenticating closure certificates;
- five-parent Truth subprotocol metadata binding without duplicate canonical authority;
- canonical ordering for set-semantic references.

## Accepted A8 dependency scope v2

A8 replaced whole-ledger staleness with fixed-point dependency-local state.

For target claim `T`, `TruthDependencyScope` contains:

- target lineage;
- same `(subject, relation)` competitors;
- transitive parent lineage of admitted competitors;
- only Evidence referenced by scoped claims;
- scoped assessments, contradictions and debt.

V2 receipts/certificates bind exact dependency scope. Unrelated Knowledge/Evidence/Verification mutations do not stale the target when they are outside the fixed point.

Global v1 remains a historical compatibility mode.

## Accepted A10 relation semantics / v3

A10 made the fixed point relation-aware through canonical Knowledge authority.

`nolane.memory.knowledge` owns:

- `RelationCardinality.EXCLUSIVE`;
- `RelationCardinality.MULTI_VALUED`;
- `RelationCardinality.UNSPECIFIED`;
- content-addressed `RelationSemanticsRevision`;
- append-only predecessor-bound `RelationSemanticsRegistry`;
- relevant-only relation-policy projection state/digest;
- additive cardinality-aware `EvidenceLedger.semantic_conflicts()`.

`external.knowledge` is therefore canonical revision `0.0.2`. A9 does not advance it further because A9 changes sidecar protocol modules rather than the canonical parent API.

### Relation law

- first relation revision is exactly `1` with no predecessor;
- later revisions increment exactly one and bind the exact predecessor digest;
- same revision rebinding fails closed;
- missing policy resolves to `UNSPECIFIED`;
- a claim cannot self-author its relation cardinality.

### Relation-aware scope v3

Binding mode:

```text
relation-aware-scope-v3
```

For active supported values sharing `(subject, relation)`:

- `EXCLUSIVE` → explicit contradiction and competing-proposition debt;
- `MULTI_VALUED` → coexistence;
- `UNSPECIFIED` → keep competitors visible and emit `relation_semantics_unspecified_for_multiple_values` debt rather than inventing exclusivity.

A v3 scope binds target/lineage/fixed-point claims, relevant Evidence, relevant relation policy projection, assessments, contradictions, debt and final canonical digest.

Verification and Assurance v3 are exact-mode; v1/v2 cannot masquerade as v3 and v3 cannot silently downgrade.

## Accepted A9 relation-aware temporal v4

A9 was numbered before A10 was accepted. Because A10 now canonically owns v3, A9 does **not** introduce the historical draft name `dependency-scope-temporal-v3`.

The canonical protocol progression is:

```text
global v1
    ↓
dependency-scope v2
    ↓
relation-aware-scope v3
    ↓
relation-aware-temporal v4
```

A9 binding mode is exactly:

```text
relation-aware-temporal-v4
```

V4 inherits A10 relation semantics and adds explicit deterministic temporal applicability.

## Explicit temporal context

`nolane.external_core.temporal_truth` provides pure value primitives only:

- strict UTC RFC3339 second-precision timestamp validation;
- `TruthInterval` using half-open `[valid_from, valid_until)` semantics;
- content-addressed `TemporalContext` with explicit caller-supplied `as_of`.

Canonical temporal derivation has no implicit clock and no default "now". `datetime.now()`, `time.time()` and local timezone inference are not canonical authorities.

At an exact upper boundary, the interval is already expired.

## Evidence temporal sidecar

`evidence_temporal_truth.py` is bound to `external.evidence` but owns no Evidence authority.

`EvidenceTemporalBinding` binds:

- exact Evidence ID;
- exact `TruthEvidence.content_digest`;
- temporal revision number;
- exact predecessor revision digest;
- validity interval;
- canonical binding digest.

`TemporalEvidenceView` preserves append-only revision history. Rules:

- first revision exactly `1`, no predecessor;
- later revision exactly `+1`;
- predecessor digest must equal the previous revision;
- base Evidence identity cannot be rebound;
- same revision semantic collision fails closed;
- restore rejects duplicate/rollback/gap/predecessor attacks.

Current evidence temporal state is:

- `missing`
- `revoked`
- `binding_mismatch`
- `not_yet_valid`
- `expired`
- `active`

Unbound legacy Evidence remains timeless; revocation remains stronger than temporal state.

## Knowledge temporal sidecar

`knowledge_temporal_truth.py` is bound to `external.knowledge` and uses the same append-only predecessor law for `KnowledgeTemporalBinding`.

A temporal revision binds the exact `KnowledgeClaim.content_digest`. Historical applicability changes do not mutate the base claim.

Required parent lineage remains visible even when a parent is not applicable. A descendant whose required parent is outside the requested horizon fails closed instead of silently dropping the parent.

## Relation-aware temporal fixed point

For explicit `TemporalContext`:

1. start with target plus complete required parent lineage;
2. only temporally active claims may create live relation competitors;
3. apply A10 relation cardinality:
   - `MULTI_VALUED` siblings may coexist;
   - `EXCLUSIVE` applicable siblings compete;
   - `UNSPECIFIED` applicable siblings remain visible for ambiguity debt;
4. each admitted competitor contributes complete parent lineage;
5. repeat to fixed point.

Therefore non-overlapping historical states do not create a present contradiction, while required historical parent failure remains auditable.

## Temporal Epistemic scope v4

`TemporalTruthRelationAwareScope` binds:

- target claim;
- complete target lineage;
- temporal relation-aware fixed-point claims;
- relevant Evidence IDs;
- relevant relation IDs;
- base scoped Knowledge digest;
- base scoped Evidence digest;
- A10 relevant relation-semantics projection digest;
- scoped Knowledge temporal projection digest;
- scoped Evidence temporal projection digest;
- `TemporalContext.digest` and exact `as_of`;
- assessments;
- contradictions;
- Epistemic/temporal/relation ambiguity debt;
- final scope digest.

`TemporalEpistemicJudge.validate_relation_aware_scope()` re-derives the complete scope from live canonical state. Serialized scope is never self-authenticating.

### Temporal debt law

A temporal claim cannot be supported through non-applicable state. Explicit debt includes, where relevant:

- `claim_not_yet_valid`
- `claim_expired`
- `parent_not_applicable`
- `evidence_not_yet_valid`
- `evidence_expired`
- `evidence_revoked`
- `evidence_binding_mismatch`
- `evidence_subject_mismatch`

A10 contradiction and ambiguity laws still apply after temporal filtering.

## Verification v4

A9 uses a dedicated `TemporalTruthVerificationReceipt`/ledger rather than adding optional temporal fields to the accepted v1/v2/v3 receipt type.

A v4 receipt exact-binds:

- claim ID;
- verifier identity and source family;
- channel and pass/fail result;
- temporal relation-aware scope digest;
- TemporalContext digest;
- canonical `as_of`;
- evidence IDs;
- content digest.

It is current only when claim, scope, context digest and `as_of` all match exactly.

Verification provenance must also be temporally active and match claim/verifier/source-family/channel. Mirrors from the same source family still count as one independent source. Negative receipts remain retained.

## Assurance v4

`TemporalTruthClosureCertificate` is a dedicated non-self-authenticating decision receipt bound to:

- claim/risk;
- exact v4 scope;
- exact v4 verification projection;
- TemporalContext digest and `as_of`;
- accepted passing receipt IDs;
- Epistemic debt IDs;
- closure result/reasons;
- content digest.

Risk requirements stay consistent with accepted Assurance:

- LOW/STANDARD → 1 independent family + 1 channel;
- HIGH → 2 + 2;
- CRITICAL → 3 + 3.

Closure blocks unsupported target, target/ancestor conflict, target/ancestor relation ambiguity, unsupported lineage, critical Epistemic debt, negative verification, invalid provenance, or insufficient verification diversity.

`validate_certificate()` recomputes canonical v4 closure from live state. Relevant Evidence revocation, temporal revision, relation-policy revision, scope change, verification change, or different `as_of` invalidates stale authority.

Unrelated temporal revisions outside the v4 fixed point do not stale the certificate.

## Compatibility law

A9 is structurally additive:

- A1–A10 `TruthEvidence` shape unchanged;
- A1–A10 `KnowledgeClaim` shape unchanged;
- v1/v2/v3 `TruthVerificationReceipt` shapes unchanged;
- v1/v2/v3 `TruthClosureCertificate` shapes unchanged;
- A8 v2 and A10 v3 behavior remain available unchanged;
- A9 sidecars declare no `COMPONENT_ID`;
- no canonical parent component version is bumped by A9;
- mixed legacy/v4 serialization fields fail closed.

The A6 five-parent subprotocol registry remains authority metadata for the canonical Truth parents; A9 sidecars do not become extra registry parents.

## Hardening lineage

- **A1** — explicit Evidence → Knowledge → Epistemic → Verification → Assurance semantics.
- **A2** — canonical snapshots, parent propagation, competing proposition retention, tamper-resistant restore.
- **A3** — anti-laundering, anti-source-rebind, replay/forgery/legacy-bypass hardening.
- **A4** — canonical parent/helper authority cleanup.
- **A5** — live authority separated from certificate content integrity.
- **A6** — five-parent Truth subprotocol metadata binding.
- **A7** — canonical set ordering.
- **A8** — dependency-scope v2 and unrelated-state stability.
- **A10** — accepted canonical relation semantics and relation-aware v3.
- **A9** — accepted explicit temporal context, append-only temporal applicability lineage and relation-aware temporal v4.

## A9 acceptance proof

A9 is accepted because the exact final candidate integrated with then-current `main` passed all canonical gates:

1. Python 3.11/3.13 compile for canonical A authorities, A1–A10 helpers and all six temporal sidecars;
2. every `tests/test_truth_knowledge_*.py`, including temporal boundary, serialization, relation inheritance and revision-lineage tests;
3. repository authority projection audit with no duplicate authority/new migration/reference debt;
4. full Refoundation Epoch 0 on Python 3.11/3.13 including 67/67 dossiers, repository audit, Refoundation contracts, Truth contracts, zero-loss evidence, organization/campaign/execution regressions and frozen Neural R2.3;
5. intended-only PR diff and no unresolved blocking review surface;
6. expected-head merge;
7. post-merge proof that canonical `main` contains the exact tested A9 tree semantics.

Canonical family-A status is therefore **A1–A10 accepted**.

Historical R-series workflows do not define current family-A architecture authority.
