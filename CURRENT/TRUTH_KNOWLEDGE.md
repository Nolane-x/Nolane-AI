# Truth / Knowledge — External Core A

Status: **A1–A12 are accepted as the canonical External Core family-A Truth / Knowledge baseline. A12 Truth Maintenance / Multiple Independent Justifications v6 was accepted from exact candidate `80d0513e152829afbfeb9b141b234c390162ede6` and merged to `main` as `ca1e8ee0f726c33a9b3e805e6713aae93a6b5c26`.**

## Canonical authority model

External Core family A remains exactly five canonical component authorities:

1. `external.evidence` → `nolane.external_core.evidence`
2. `external.knowledge` → `nolane.memory.knowledge`
3. `external.epistemic` → `nolane.external_core.epistemic`
4. `external.verification` → `nolane.external_core.verification`
5. `external.assurance` → `nolane.external_core.assurance`

Truth Closure is additive protocol semantics beneath those authorities. No Truth, Temporal, Provenance, or Justification helper may declare `COMPONENT_ID`.

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

The canonical protocol progression before A11 is:

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

## Accepted A11 — provenance-bound source independence v5

A11 closes a remaining authority hole in v1–v4 independence counting. Historical verification can bind a `source_family`, and `EvidenceLedger` prevents one `source_id` from rebinding that family, but multiple source identities controlled by the same real origin can still present distinct family labels. That can falsely look like independent corroboration.

A11 therefore makes source independence a canonical provenance-lineage property rather than a receipt label.

The accepted progression through A11 is:

```text
global v1
    ↓
dependency-scope v2
    ↓
relation-aware-scope v3
    ↓
relation-aware-temporal v4
    ↓
provenance-lineage-temporal v5
```

V5 binding mode is exactly:

```text
provenance-lineage-temporal-v5
```

### Evidence source-provenance lineage

`evidence_provenance_truth.py` is a sidecar under `external.evidence` and owns no sixth authority.

`SourceProvenanceRevision` binds:

- protocol domain `truth-source-provenance-v5`;
- `source_id`;
- strictly monotonic revision;
- exact predecessor digest;
- explicit `controller_id`;
- canonical parent-source IDs;
- canonical digest.

`SourceProvenanceRegistry` enforces:

- first revision exactly `1` with no predecessor;
- later revision exactly `+1`;
- exact predecessor binding;
- existing parents only;
- no direct or transitive source cycle;
- no revision rebinding;
- duplicate/gap/rollback/predecessor/cycle restore attacks fail closed;
- cross-protocol revision restore fails closed.

For source `S`, the current controller-root set is the union of its own controller and every transitive provenance ancestor controller.

A source contributes an independent verification identity only when that set contains exactly one controller. Therefore:

- aliases under one controller collapse;
- same-controller mirrors/transforms collapse;
- multi-controller aggregates remain auditable but mint no new independent-source credit;
- missing canonical provenance contributes no independence.

The relevant projection contains requested sources plus all transitive provenance ancestors. Unrelated source revisions outside that ancestry cannot stale the projection; relevant source or ancestor revision must stale it.

### Epistemic v5 scope

`epistemic_provenance_truth.py` does not duplicate A9 fixed-point logic. `ProvenanceEpistemicJudge` first re-derives the exact accepted `TemporalEpistemicJudge.relation_aware_dependency_scope()` result, derives source IDs from its exact Evidence fixed point, and then binds the relevant source-provenance projection.

`ProvenanceTruthScope` therefore exact-binds:

- target claim;
- exact v4 temporal scope digest;
- TemporalContext digest and `as_of`;
- scoped source IDs;
- relevant source-provenance projection digest;
- final v5 digest.

Validation re-derives all live state. Serialized v5 scope is never self-authenticating.

### Verification v5

`ProvenanceTruthVerificationReceipt` is a dedicated v5 receipt and deliberately contains **no `source_family` field**.

It binds verifier/source identity, channel, pass/fail result, exact v5 scope/context, verification Evidence IDs and the verifier's relevant provenance projection digest.

Coverage validates live temporal Evidence and exact subject/source/channel provenance, validates the live source-provenance projection, retains negative receipts, and groups passing independence only by `SourceProvenanceRegistry.independence_key(verifier_id)`.

A multi-controller source can remain a valid audit receipt while contributing zero independence credit.

In addition, every controller root already represented by an Evidence source in the exact epistemic v5 scope is an origin controller. A passing verifier whose independence key is one of those origin controllers remains retained and auditable but is placed in `non_independent_receipt_ids` and contributes zero independent-source credit. This prevents claim-producing evidence and its own controller aliases from self-certifying as independent verification.

### Assurance v5

`ProvenanceTruthAssuranceGate` preserves the accepted A9 relation/temporal/Epistemic/debt/negative-verification vetoes and the existing risk thresholds:

- LOW/STANDARD → 1 independent controller + 1 channel;
- HIGH → 2 + 2;
- CRITICAL → 3 + 3.

The semantic change is that source diversity now comes from canonical provenance-derived controller independence, not caller-declared family labels.

A v5 certificate exact-binds v5 scope, v5 verification projection, context/as-of, accepted receipt IDs, Epistemic debt IDs, decision and reasons. `validate_certificate()` recomputes complete live closure.

Relevant verifier provenance revision invalidates stale authority. Unrelated provenance mutation does not.

## Accepted A12 — truth maintenance / multiple independent justifications v6

A11 secures who is independent. A12 addresses the next Knowledge semantics gap: one accepted `KnowledgeClaim` historically has one conjunction of `evidence_ids` and `parent_claim_ids`, so failure of any member invalidates that single derivation. Real propositions can have several alternative derivations, but introducing OR semantics without a canonical truth-maintenance layer would create proof laundering and stale-authority hazards.

A12 therefore adds an additive v6 derivation sidecar while leaving every A1–A11 identity and protocol unchanged.

The canonical progression through A12 is:

```text
global v1
    ↓
dependency-scope v2
    ↓
relation-aware-scope v3
    ↓
relation-aware-temporal v4
    ↓
provenance-lineage-temporal v5
    ↓
justification-provenance-lineage-temporal v6
```

V6 binding mode is exactly:

```text
justification-provenance-lineage-temporal-v6
```

### Knowledge justification sidecar

`knowledge_justification_truth.py` is a sidecar under `external.knowledge` and owns no sixth authority.

Every canonical `KnowledgeClaim` contributes one deterministic implicit legacy basis containing exactly its accepted `evidence_ids` and `parent_claim_ids`. A12 may add explicit `KnowledgeJustificationRevision` lineages, but does not rewrite the base claim.

A justification is one conjunction:

```text
J = evidence_1 AND ... AND evidence_n AND parent_1 AND ... AND parent_m
```

The claim is a disjunction across its implicit legacy basis and enabled explicit bases:

```text
claim = J_legacy OR J_1 OR J_2 OR ...
```

The OR is a liveness/derivation law only. It cannot mint source-independence, verifier, confidence, or assurance credit.

`KnowledgeJustificationRegistry` enforces:

- revision 1 exactly, with no predecessor;
- later revisions exactly `+1` and exact predecessor digest;
- exact claim ID and `KnowledgeClaim.content_digest` binding;
- no claim/digest lineage rebind;
- canonical unique evidence/parent sets;
- existing parent claims only;
- no self-parent or effective justification dependency cycle;
- no duplicate live explicit basis;
- no explicit duplication of the implicit legacy basis;
- duplicate/gap/predecessor/domain attacks fail closed on restore;
- relevant-only projection state/digest.

### OR-of-AND Epistemic v6

Each effective basis is evaluated independently at the exact A9 temporal context.

Inside one basis, AND is strict: every required parent must be temporally active and `SUPPORTED`, and every required Evidence row must be active and bind the exact claim. If one required member fails, that path is `dead`; another path may still keep the proposition live.

A live path is classified as:

- `supported` for support-only evidence;
- `refuted` for refute-only evidence;
- `contradicted` for support and refute together;
- `unknown` when it contains no decisive evidence;
- `dead` when a required member is unavailable, mismatched, temporally inapplicable, revoked, or unsupported.

Claim aggregation is fail-visible:

- any supported path plus any refuted/contradicted path → `CONTRADICTED`;
- otherwise at least one supported path → `SUPPORTED`;
- otherwise at least one contradicted path → `CONTRADICTED`;
- otherwise at least one refuted path → `REFUTED`;
- otherwise → `UNKNOWN`.

Therefore an alternative support path cannot hide a live refutation.

### Audit lineage versus contributing lineage

A12 deliberately separates two graphs:

1. **audit/fixed-point lineage** retains every enabled alternative, its parent lineage, relevant Evidence, relation competitors and source provenance so stale state cannot disappear from the canonical projection;
2. **contributing live lineage** is derived only by starting at the target and following justification statuses that are actually `supported`.

This distinction is required for correct OR semantics.

A parent that appears only on a dead alternative remains visible in the scope and can stale the scope when its relevant state changes, but it does not veto closure of a different live branch. Conversely, a parent on a live supported path remains mandatory and its loss invalidates that path and any certificate depending on it.

The same contribution trace defines `supporting_source_ids`: only Evidence sources reached through target-contributing supported paths become verifier origin exclusions. Sources that occur only on dead alternatives remain auditable but cannot falsely reduce verification independence.

### Epistemic scope v6

`JustificationTruthScope` binds:

- target claim;
- full A12 audit lineage;
- relation-aware temporal fixed-point claims;
- all relevant justification Evidence IDs;
- relevant relation IDs;
- scoped base Knowledge and Evidence digests;
- relevant relation-semantics projection;
- relevant Knowledge/Evidence temporal projections;
- relevant justification projection;
- all relevant source IDs;
- target-contributing supporting source IDs;
- relevant source-provenance projection;
- explicit TemporalContext digest and `as_of`;
- per-claim assessments;
- per-justification statuses/reasons;
- contradictions and epistemic debt;
- final v6 digest.

`JustificationEpistemicJudge.validate_scope()` re-derives the scope from live canonical state. An unrelated justification revision outside the fixed point does not stale the scope; a relevant revision does.

### Verification v6

A12 uses a dedicated `JustificationTruthVerificationReceipt` and ledger. A v5 receipt cannot masquerade as v6 and v6 cannot silently downgrade.

A v6 receipt exact-binds claim, verifier, channel, pass/fail result, v6 scope, temporal context/as-of, verification Evidence IDs and verifier provenance projection. Negative results remain retained.

Coverage preserves A11 source-provenance validation and controller-derived independence. A verifier under any controller root of a target-contributing supporting source remains auditable but receives zero independence credit. Controllers found only on dead/non-contributing paths are not false origin exclusions.

### Assurance v6

Risk thresholds remain unchanged:

- LOW/STANDARD → 1 independent controller + 1 channel;
- HIGH → 2 + 2;
- CRITICAL → 3 + 3.

Closure blocks unsupported/contradicted target, conflict/ambiguity/critical debt on the contributing live lineage, incomplete relevant source provenance, invalid/negative verification, or insufficient independent verifier/channel diversity.

Dead alternatives remain audit-visible but cannot veto a separate live OR branch. A parent that contributes through a supported path remains mandatory.

`JustificationTruthClosureCertificate` is non-self-authenticating. Validation recomputes canonical v6 scope and closure from live state, so relevant justification changes stale certificates even when the final boolean decision happens to remain the same; unrelated justification changes do not.

## Compatibility law

A11 remains structurally additive and accepted:

- A1–A10 `TruthEvidence` shape unchanged;
- A1–A10 `KnowledgeClaim` shape unchanged;
- v1/v2/v3 receipts and certificates unchanged;
- v4 temporal receipts and certificates unchanged;
- historical `source_family` behavior remains v1–v4 compatibility only;
- v5 receipt rejects unexpected legacy `source_family` state;
- A11 sidecars declare only `PARENT_COMPONENT_ID`, never `COMPONENT_ID`;
- no canonical parent component version is bumped solely by A11;
- family A remains exactly five canonical authorities.

A12 preserves the same compatibility boundary:

- `TruthEvidence` and `KnowledgeClaim` historical shapes are unchanged;
- implicit legacy justification reproduces the accepted A11/A9 epistemic result when no explicit A12 rows exist;
- v1–v5 receipts/certificates remain historical exact modes and do not read v6 state;
- all four A12 modules declare only `PARENT_COMPONENT_ID` under their accepted parent authority;
- no canonical family-A component revision is advanced solely because the v6 sidecars exist;
- family A remains exactly five authorities.

The A6 five-parent subprotocol registry remains authority metadata for canonical Truth parents; temporal/provenance/justification sidecars do not become registry parents.

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
- **A11** — accepted append-only source-provenance lineage, protocol-domain separation, controller-derived verification independence, and origin-controller self-verification exclusion v5.
- **A12** — accepted append-only alternative justification lineage, OR-of-AND truth maintenance, contribution-traced live lineage/source origins, and relevant-only v6 staleness.

## A9 acceptance proof

A9 is accepted because the exact final candidate integrated with then-current `main` passed all canonical gates:

1. Python 3.11/3.13 compile for canonical A authorities, A1–A10 helpers and all six temporal sidecars;
2. every `tests/test_truth_knowledge_*.py`, including temporal boundary, serialization, relation inheritance and revision-lineage tests;
3. repository authority projection audit with no duplicate authority/new migration/reference debt;
4. full Refoundation Epoch 0 on Python 3.11/3.13 including 67/67 dossiers, repository audit, Refoundation contracts, Truth contracts, zero-loss evidence, organization/campaign/execution regressions and frozen Neural R2.3;
5. intended-only PR diff and no unresolved blocking review surface;
6. expected-head merge;
7. post-merge proof that canonical `main` contains the exact tested A9 tree semantics.

## A11 acceptance proof

A11 is accepted from exact final candidate `e5b2aa3b8e7ad9e389889c90129939b741d10079`.

The acceptance chain is explicit:

1. Initial RED at `3b94b249e09c64313838b08179daa7b499b52ccf` proved A11 production did not yet exist while existing A compile remained green.
2. Source-provenance, v5 epistemic scope, v5 verification and v5 assurance were implemented additively without creating canonical authority.
3. A domain-separation RED produced 121 pass / 1 targeted failure; the fix bound `truth-source-provenance-v5` into revision digest/state and made foreign-protocol restore fail closed.
4. A claim-origin-independence RED at `3e398be35c6a66926714f8f58d548547d35a8850` produced 122 pass / 1 targeted failure because a verifier under the claim evidence controller was incorrectly counted as a third independent source.
5. Exact final candidate `e5b2aa3b8e7ad9e389889c90129939b741d10079` corrected that by excluding epistemic-scope origin controllers from independent verification credit while retaining their receipts for audit.
6. Truth Knowledge A Layer run `33354072239` passed on Python 3.11 and 3.13. Python 3.13 fresh log reports **123 passed** and repository audit `173 historical artifacts; 173 moved / 0 quarantined; 0 with reference debt; 1 non-native component records`.
7. Full Refoundation Epoch 0 run `33354075422` passed on Python 3.11 and 3.13, including canonical compile, 67/67 dossiers, repository audit, Refoundation contracts, Truth Knowledge contracts, zero-loss evidence generation/upload, all organization/campaign/execution regressions, and frozen Neural R2.3 metadata verification.
8. PR #269 had an intended A11-only 12-file diff, was mergeable, and had 0 reviews / 0 review threads blocking acceptance.
9. PR #269 was merged with expected-head protection from exact head `e5b2aa3b8e7ad9e389889c90129939b741d10079`.
10. Canonical `main` advanced to merge commit `b44f3601c14ad6039faeee2565b412fc60832e8c`, whose parents are the then-current `main` and the exact tested A11 candidate.

## A12 acceptance proof

A12 is accepted from exact final candidate `80d0513e152829afbfeb9b141b234c390162ede6`.

The acceptance chain is explicit:

1. Initial RED head `5df53b695cdbc279fcae62591f27ce6365b2b412`, run `33355398941`: accepted A1–A11 compile stayed green and collection failed exactly because the v6 assurance sidecar did not exist yet.
2. The first complete v6 implementation reached focused GREEN at head `0b50e416c63bc788e16b58b619d4ced7ca4c9071`, run `33355739175`: Python 3.11/3.13 passed **133 Truth/Knowledge tests** and repository audit stayed clean.
3. Contribution-origin RED head `62698ca01124b8518682810a04271e131e4b8b36`, run `33355810736`: **133 passed / 1 targeted failure** proved a supported parent that existed only through a dead target path was incorrectly entering `supporting_source_ids`.
4. Contribution-trace fix head `e5ec35a5cf50fdbb6e6ebbe7460233874a7f5777`, run `33355924680`, restored focused GREEN by tracing supporting Evidence only through target-reachable `supported` justification paths.
5. Authority/domain/legacy-equivalence contracts prove exact parent ownership, no `COMPONENT_ID`, v6 protocol separation, anti-rebind behavior, and that no explicit justification preserves the accepted A11/A9 epistemic semantics.
6. Dead-branch assurance RED head `fbe6071616bc2979e4a6fcc85b901a4c99ff1bbe`, run `33356064294`: **138 passed / 1 targeted failure** proved an unsupported parent reachable only through a dead alternative could still veto a live target branch.
7. Supporting-lineage fix head `6f241b9ea928eef7e8b3bb8e7ac46f9bfa1046a8` derives assurance veto lineage only from target-reachable `supported` paths while retaining the full alternative graph for audit and staleness. Python 3.11 fresh log in run `33356186788` reports **139 passed** and repository audit `173 historical artifacts; 173 moved / 0 quarantined; 0 with reference debt; 1 non-native component records`.
8. Head `475e094fbd485b09972742e8c25b22a292fc5bc3` added final regression contracts proving the inverse boundary: a parent on a live supported path remains mandatory, unrelated justification revisions preserve scope/certificate validity, and relevant revisions stale both.
9. Exact final candidate `80d0513e152829afbfeb9b141b234c390162ede6` passed Truth Knowledge A Layer run `33356450779` on Python 3.11 and 3.13: **141/141 Truth/Knowledge tests** on both versions, direct compile of all four A12 sidecars, and repository audit `173 historical artifacts; 173 moved / 0 quarantined; 0 with reference debt; 1 non-native component records`.
10. PR #273 synthetic merge commit `34ccf629f98e25ac654fa1c3f15e882f59110820` merged exact head `80d0513e152829afbfeb9b141b234c390162ede6` into exact base `0c1beb3e16a5c502793f8d1fd0e592022ee5554c`. Full Refoundation Epoch 0 run `33356534176` passed on Python 3.11 and 3.13: **653 Refoundation + 141 Truth A + 413 downstream tests**, 67/67 dossiers, clean repository audit, zero-loss evidence gates, all organization/campaign/execution regressions, and frozen Neural R2.3 PASS.
11. PR #273 had the intended A12-only 13-file diff, was `mergeable=true` / `mergeable_state=clean`, and had 0 reviews and 0 inline review comments blocking acceptance.
12. PR #273 was merged with expected-head protection from exact head `80d0513e152829afbfeb9b141b234c390162ede6`.
13. Canonical `main` advanced to production merge commit `ca1e8ee0f726c33a9b3e805e6713aae93a6b5c26`, whose exact parents are pre-A12 `main` `0c1beb3e16a5c502793f8d1fd0e592022ee5554c` and exact tested A12 candidate `80d0513e152829afbfeb9b141b234c390162ede6`.

Canonical family-A status at this revision is therefore **A1–A12 accepted**.

Historical R-series workflows do not define current family-A architecture authority.