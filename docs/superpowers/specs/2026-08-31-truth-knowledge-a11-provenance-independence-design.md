# A11 Provenance-Bound Source Independence — Design

## Status

Design for the next External Core family-A hardening wave after the accepted A1–A10 baseline.

## Problem

A1–A10 correctly bind Evidence provenance fields, reject source-family rebinding, deduplicate passing verification by `source_family`, and revalidate live evidence. However, `source_family` is still a field supplied on Evidence/Verification records. Three aliases controlled by one real origin can therefore be presented as three different families and appear to satisfy HIGH/CRITICAL independence thresholds.

This is an authority problem, not a scoring problem. Adding confidence weights before fixing identity would only attach false precision to untrusted independence claims.

## Goal

Introduce an additive A11 protocol generation in which verification independence is derived from canonical source-provenance lineage rather than caller-declared family labels, while preserving v1–v4 identities and the existing five canonical family-A authorities.

## Authority boundary

Family A remains exactly:

1. `external.evidence`
2. `external.knowledge`
3. `external.epistemic`
4. `external.verification`
5. `external.assurance`

A11 helpers declare `PARENT_COMPONENT_ID` only and MUST NOT declare `COMPONENT_ID`.

`external.evidence` remains the canonical owner of source provenance. A11 does not create a sixth authority and does not import Nolane World runtime objects as Nolane AI authority.

## Protocol progression

```text
global v1
  -> dependency-scope v2
  -> relation-aware-scope v3
  -> relation-aware-temporal v4
  -> provenance-lineage-temporal v5
```

The v5 binding mode is exactly:

```text
provenance-lineage-temporal-v5
```

## Evidence provenance sidecar

Create `nolane.external_core.evidence_provenance_truth`.

### SourceProvenanceRevision

Each revision binds:

- `source_id`
- strictly monotonic `revision`
- exact `predecessor_digest`
- explicit `controller_id`
- canonical set of `parent_source_ids`
- content digest

Rules:

- first revision is exactly 1 with no predecessor;
- later revisions are exactly previous revision + 1;
- predecessor digest must match the exact current predecessor;
- a source cannot directly or transitively parent itself;
- every parent must already exist in the registry;
- same `(source_id, revision)` cannot be rebound;
- restore rejects duplicate rows, gaps, rollback, predecessor mismatch and cycles.

### Independence semantics

For the current revision of source `S`, recursively compute its controller root set:

```text
roots(S) = {S.controller_id} union roots(parent_1) union ... union roots(parent_n)
```

A source contributes one independent identity only when `roots(S)` contains exactly one controller. Its independence key is that controller ID.

Consequences:

- multiple aliases under one controller collapse to one independent source;
- same-controller mirrors/transforms collapse to one source;
- an aggregate/derived source spanning multiple controllers remains auditable but does not mint a new independent source;
- a source whose provenance is missing cannot contribute independence.

This is intentionally conservative. Independence is relative to the canonical Evidence provenance registry supplied by the runtime; verification receipts cannot self-author this registry state.

### Relevant-only projection

`SourceProvenanceRegistry.projection_state(source_ids)` includes the requested sources plus every transitive provenance ancestor, in canonical order. Missing requested source IDs are explicit `missing` rows.

Unrelated source revisions outside the requested ancestry MUST NOT change the projection digest. A relevant source/ancestor revision MUST change it.

## Epistemic v5 wrapper scope

Create `nolane.external_core.epistemic_provenance_truth`.

`ProvenanceTruthScope` wraps the exact live A9 `TemporalTruthRelationAwareScope` rather than duplicating its relation/temporal algorithms. It binds:

- target claim ID;
- exact v4 temporal scope digest;
- temporal context digest and `as_of`;
- canonical source IDs referenced by scoped Evidence;
- relevant source-provenance projection digest;
- final v5 scope digest.

`ProvenanceEpistemicJudge.relation_aware_temporal_scope()` MUST first re-derive the canonical v4 scope, then derive source IDs from its exact Evidence fixed point, then bind the relevant provenance projection.

Validation re-derives all of the above from live canonical A state. Serialized v5 scope is never self-authenticating.

## Verification v5

Create `nolane.external_core.verification_provenance_truth`.

`ProvenanceTruthVerificationReceipt` is a dedicated v5 receipt. It MUST NOT contain `source_family`.

It binds:

- receipt ID;
- claim ID;
- verifier/source ID;
- channel;
- pass/fail result;
- exact v5 scope digest;
- exact temporal context digest and `as_of`;
- verification Evidence IDs;
- exact relevant verifier provenance projection digest;
- content digest.

Coverage validates:

1. exact v5 scope/context binding;
2. verification Evidence is temporally active;
3. evidence subject/source/channel exactly matches the receipt;
4. receipt provenance digest equals the live relevant provenance projection;
5. provenance for the verifier exists.

Valid passing receipts are grouped by `SourceProvenanceRegistry.independence_key(verifier_id)`, never by caller labels.

A valid source with multi-controller roots may remain in the audit receipt set but contributes no independent count. Missing/stale provenance makes the receipt invalid.

Negative receipts remain retained.

## Assurance v5

Create `nolane.external_core.assurance_provenance_truth`.

`ProvenanceTruthClosureCertificate` binds:

- claim/risk;
- exact v5 scope digest;
- exact v5 verification projection digest;
- temporal context digest and `as_of`;
- accepted passing receipt IDs;
- epistemic debt IDs;
- closure result/reasons;
- content digest.

Risk thresholds stay unchanged:

- LOW/STANDARD: 1 independent controller + 1 channel;
- HIGH: 2 + 2;
- CRITICAL: 3 + 3.

The difference is that independent-source count comes only from provenance-derived independence keys.

Closure additionally fails when scoped Evidence source provenance is incomplete. Existing A9 relation, temporal, epistemic, negative-verification and channel-diversity vetoes remain intact.

`validate_certificate()` fully recomputes live v5 closure. Relevant source-provenance revision, ancestor revision, Evidence/Knowledge/relation/temporal change, verification change, or different `as_of` invalidates stale authority. Unrelated provenance revisions do not.

## Compatibility

A11 is additive:

- A1–A10 Evidence/Knowledge record shapes unchanged;
- v1/v2/v3 receipt/certificate shapes unchanged;
- v4 temporal receipt/certificate shapes unchanged;
- existing `source_family` behavior remains historical v1–v4 compatibility only;
- v5 receipt explicitly rejects legacy `source_family` fields on restore;
- no canonical parent component version is advanced solely for a sidecar protocol;
- no A11 helper declares `COMPONENT_ID`.

## Adversarial acceptance contracts

A11 is not accepted until tests prove at minimum:

1. same-controller aliases collapse to one independent identity;
2. same-controller mirrors do not mint independence;
3. multi-controller aggregates do not mint independence;
4. provenance cycle, gap, rollback, predecessor mismatch and rebind fail closed;
5. relevant-only projection is stable under unrelated revisions and changes under relevant revisions;
6. v5 receipt rejects self-asserted/legacy `source_family` state;
7. three verifier aliases under one controller cannot close a CRITICAL claim;
8. three genuinely distinct canonical controller roots across three channels can close the same CRITICAL claim;
9. changing relevant verifier provenance invalidates an existing v5 certificate;
10. unrelated provenance change does not invalidate it;
11. all A1–A10 Truth/Knowledge contracts remain GREEN on Python 3.11 and 3.13;
12. full Refoundation Epoch 0 remains GREEN on Python 3.11 and 3.13.

## Deferred waves

A11 deliberately does not add numeric confidence or multiple alternative derivation justifications. Those are independent authority problems:

- A12: truth-maintenance / multiple independent justifications and retraction survival;
- A13: calibrated evidence quality, correlation-aware weighting and Goodhart-resistant measurement.

They should be implemented only after provenance identity is trustworthy.