# A13 Defeasible Truth Maintenance / Justification Undercutters v7 Design

## Status

Candidate design for External Core family A. A1–A12 remain the accepted baseline until A13 completes RED/GREEN proof, exact-head CI, merge-state Refoundation, expected-head production merge, and a separate acceptance seal.

## Problem

A12 adds multiple independent justification paths, but every path is still monotonic with respect to its own premises: if its evidence and parent claims remain live, the path remains admissible. There is no canonical way to express that the *inference itself* has been invalidated while the original evidence remains historically valid.

Examples include a discovered confounder, invalid measurement protocol, broken inference rule, scope mismatch, or methodological flaw. Revoking the original evidence is semantically wrong when the observation itself remains genuine. Adding ordinary refuting evidence is also different: a rebuttal attacks the proposition, while an undercutter attacks one derivation.

A13 closes that hole without mutating A1–A12 identities and without creating a sixth authority.

## Authority law

Family A remains exactly five canonical authorities:

1. `external.evidence`
2. `external.knowledge`
3. `external.epistemic`
4. `external.verification`
5. `external.assurance`

All A13 modules are sidecars and declare `PARENT_COMPONENT_ID`, never `COMPONENT_ID`.

## Canonical protocol progression

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
    ↓
defeasible-justification-provenance-lineage-temporal v7
```

Exact v7 binding mode:

```text
defeasible-justification-provenance-lineage-temporal-v7
```

## Knowledge undercutter sidecar

`nolane.external_core.knowledge_undercutter_truth` is owned by `external.knowledge`.

A `JustificationUndercutterRevision` binds:

- immutable `undercutter_id`;
- exact target claim ID and `KnowledgeClaim.content_digest`;
- exact target justification ID;
- exact target `KnowledgeJustificationBasis.digest`;
- strict revision number and exact predecessor digest;
- canonical evidence IDs;
- canonical parent-claim IDs;
- enabled state;
- canonical digest.

An undercutter basis must contain at least one evidence ID or parent claim. Empty attacks are forbidden.

The target justification must be a currently effective A12 basis when the first undercutter revision is registered. An undercutter cannot target a different claim or silently follow a rewritten justification basis. If the target basis later changes, the old undercutter remains auditable but is not allowed to defeat the new basis.

### Revision law

- first revision is exactly `1` and has no predecessor;
- later revisions advance exactly `+1`;
- predecessor digest must equal the exact previous revision digest;
- target claim, target claim digest, target justification ID, and target basis digest are lineage-immutable;
- same-revision rebinding fails closed;
- restore rejects duplicate, gap, rollback, predecessor, domain, and binding attacks.

### Dependency-cycle law

A13 evaluates claim support and undercutter support in one dependency universe. The effective graph contains edges from each claim to:

- every parent in every effective A12 justification; and
- every parent in every enabled undercutter targeting one of that claim's effective justifications.

Registration fails if this combined graph contains a direct or transitive cycle. An undercutter may not depend on its own target claim.

## Undercutter epistemic law

An undercutter is an AND basis over its parents and evidence.

Parent claims must be temporally active and `SUPPORTED`. Evidence must be temporally active, bind `subject_id == undercutter_id`, and retain ordinary A1 provenance/polarity semantics.

Intrinsic undercutter status:

- support evidence only → `supported`;
- refute evidence only → `refuted`;
- support + refute → `contradicted`;
- no decisive evidence → `unknown`;
- missing/revoked/expired/binding-mismatched evidence or unavailable parent → `dead`.

Only a `supported` undercutter defeats its exact bound justification basis.

A `contradicted` undercutter makes that path `contested`: the attack itself is disputed, so the path is not allowed to masquerade as clean support when it is the only candidate path.

A `refuted` undercutter does not defeat the path.

An `unknown` undercutter does not defeat or contest the path. It creates explicit epistemic debt but cannot denial-of-service canonical truth merely by existing.

## Defeasible justification status

V7 uses a dedicated status type; v6 serialized status is never widened in place.

Each v7 justification status binds:

- intrinsic A12-style status;
- final v7 status;
- exact active/contested undercutter IDs;
- basis evidence/parents;
- canonical digest.

Final status set:

- `supported`
- `refuted`
- `contradicted`
- `unknown`
- `dead`
- `defeated`
- `contested`

Rules:

1. intrinsically dead stays `dead`;
2. any supported exact-bound undercutter makes a non-dead path `defeated`;
3. otherwise any contradicted exact-bound undercutter makes a non-dead path `contested`;
4. otherwise intrinsic status is preserved.

## Claim aggregation

Across final path statuses:

1. any clean `supported` path plus any clean `refuted` or `contradicted` path → `CONTRADICTED`;
2. else any clean `supported` path → `SUPPORTED`;
3. else any `contradicted` path → `CONTRADICTED`;
4. else any `refuted` path plus any `contested` path → `CONTRADICTED`;
5. else any `refuted` path → `REFUTED`;
6. else → `UNKNOWN`.

`defeated`, `dead`, and `unknown` paths do not mint support or refutation. `contested` alone produces no proposition truth.

This preserves A12's fail-visible live refutation while allowing a *canonically supported attack on the derivation itself* to remove an invalid path.

## V7 fixed point and projection

The v7 scope starts from the target and repeatedly closes over:

- A12 effective justification parents;
- enabled undercutter parent claims for effective bases;
- temporally active relation competitors according to A10 cardinality;
- every parent lineage introduced by those competitors and their undercutters.

The scope binds:

- target, lineage, and full audit claim set;
- base Knowledge/Evidence scoped digests;
- relation semantics projection;
- temporal Knowledge/Evidence projections;
- A12 justification projection;
- A13 undercutter projection;
- full audit Evidence and source IDs;
- decision-source IDs;
- provenance projection;
- per-claim assessments;
- per-justification v7 statuses;
- per-undercutter statuses;
- contradictions and epistemic debt;
- explicit `TemporalContext` and exact `as_of`;
- final v7 digest.

Unrelated undercutter revisions outside the fixed point do not stale the target. Relevant undercutter revisions do.

## Decision-source trace

A11/A12 prevent a controller that produced live claim support from self-certifying as independent verification. V7 generalizes this to derivation attacks.

`decision_source_ids` include source identities for:

- support evidence on target-reachable clean supported justification paths; and
- decisive evidence belonging to undercutters attached to those supporting-lineage claims.

This is intentionally conservative: a source that materially shapes whether a derivation is accepted cannot immediately reappear as an independent verifier of the resulting decision.

Sources that exist only on unrelated claims remain outside the relevant projection.

## Verification v7

`verification_defeasible_truth.py` owns dedicated v7 receipts and projection. A v6 receipt cannot masquerade as v7.

A v7 receipt binds the exact v7 scope/context/as-of, verifier source, channel, verification Evidence, exact verifier provenance projection, and pass/fail result.

Coverage retains negative receipts and derives independence only from canonical provenance controller roots. Any controller represented by `decision_source_ids` contributes zero independent verification credit.

## Assurance v7

`assurance_defeasible_truth.py` owns dedicated v7 closure certificates.

Risk thresholds stay unchanged:

- LOW/STANDARD → 1 independent controller + 1 channel;
- HIGH → 2 + 2;
- CRITICAL → 3 + 3.

Supporting lineage follows only final `supported` justification paths. Dead, defeated, contested, refuted, and unrelated alternative branches remain auditable but cannot veto a live OR branch merely by existing.

Closure still blocks target/lineage contradiction, relation ambiguity, unsupported live lineage, critical debt, invalid provenance, negative verification, and insufficient diversity.

For CRITICAL claims, unresolved undercutter debt on the supporting lineage is critical and therefore blocks closure. Unknown attacks on lower-risk claims remain auditable but do not automatically create an attack-spam denial of service.

Certificates are non-self-authenticating and validate only by recomputing complete live v7 state.

## Compatibility

- A1–A12 protocols and serialized forms remain byte/domain separated.
- With no A13 undercutters, v7 epistemic dispositions and live-support lineage must match accepted A12 semantics.
- V6 receipts/certificates are never accepted as v7 artifacts.
- No existing canonical component revision is advanced solely because sidecar v7 exists.

## Acceptance gates

A13 is not accepted until all of the following are fresh on one frozen exact candidate head:

1. focused Truth/Knowledge CI on Python 3.11 and 3.13;
2. repository authority audit clean;
3. intended-only diff and clean review surface;
4. full Refoundation Epoch 0 on the PR synthetic merge state for Python 3.11 and 3.13;
5. expected-head production merge;
6. post-merge tree verification;
7. separate doc-only acceptance seal with fresh Truth/Knowledge and full Refoundation merge-state proof.
