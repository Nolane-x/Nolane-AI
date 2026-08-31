# A14 Truth / Knowledge — Source Dependence / Common-Basis Independence v8 Design

## Status

Design authority for the A14 Family-A hardening wave. A13 remains the accepted canonical baseline until A14 completes RED→GREEN, exact-head CI, current-main merge-state CI, expected-head production merge, and a separate acceptance seal.

## Problem

A11 made verification independence provenance-controller aware. A13 extended the decision-origin trace to decisive undercutters and their supported parent lineage. That prevents aliases and same-controller actors from self-certifying, but v7 still treats two distinct controller roots as independent even when their verification evidence is generated from the same epistemic basis: the same dataset, instrument, measurement run, benchmark corpus, upstream observation batch, or other common cause.

Controller independence is organizational independence, not epistemic independence. A14 must represent common-basis dependence canonically and make verification independence conservative under that information.

## Non-goals

- Do not modify accepted v1–v7 types or protocols.
- Do not add a sixth canonical Family-A authority.
- Do not invent probabilistic confidence scores.
- Do not infer hidden dependence from payload similarity.
- Do not make unrelated dependence revisions stale a target.
- Do not let an unclassified source mint v8 independence credit.

## Authority model

Family A remains exactly five canonical authorities:

1. `external.evidence`
2. `external.knowledge`
3. `external.epistemic`
4. `external.verification`
5. `external.assurance`

A14 adds four sidecars only:

- `evidence_dependence_truth.py` → `PARENT_COMPONENT_ID = "external.evidence"`
- `epistemic_dependence_truth.py` → `PARENT_COMPONENT_ID = "external.epistemic"`
- `verification_dependence_truth.py` → `PARENT_COMPONENT_ID = "external.verification"`
- `assurance_dependence_truth.py` → `PARENT_COMPONENT_ID = "external.assurance"`

None may declare `COMPONENT_ID`.

## Protocol progression

A14 binding mode is exactly:

```text
dependence-defeasible-justification-provenance-lineage-temporal-v8
```

The canonical progression becomes:

```text
global v1
  → dependency-scope v2
  → relation-aware-scope v3
  → relation-aware-temporal v4
  → provenance-lineage-temporal v5
  → justification-provenance-lineage-temporal v6
  → defeasible-justification-provenance-lineage-temporal v7
  → dependence-defeasible-justification-provenance-lineage-temporal v8
```

## Evidence dependence sidecar

`SourceDependenceRevision` is append-only and content-addressed. It binds:

- `source_id`
- positive `revision`
- exact `predecessor_digest`
- canonical, explicit, non-empty `basis_ids`
- canonical digest under protocol `truth-source-dependence-v8`

Rules:

- first revision is exactly 1 and has no predecessor;
- later revisions advance exactly +1 and bind the exact predecessor digest;
- same revision semantic collision fails closed;
- serialized duplicates/gaps/rollback/predecessor mismatch fail closed;
- `basis_ids` are set-semantic, unique, sorted and non-empty;
- a revision may change dependence bases, but doing so changes all relevant v8 projections and therefore stales v8 receipts/certificates;
- missing source dependence is explicit missing state, never implicit independence.

`SourceDependenceRegistry.projection_state(source_ids)` contains only requested sources. An unrelated source revision does not change the projection digest.

## Epistemic v8 scope

A14 does not reimplement A13 truth maintenance. `DependenceEpistemicJudge` first recomputes the exact live `DefeasibleEpistemicJudge` scope, then binds the dependence projection for all `scope.source_ids`.

`DependenceTruthScope` exact-binds:

- target claim ID;
- exact v7 scope state and digest;
- temporal context digest and `as_of`;
- audit source IDs and decision source IDs copied from v7;
- relevant source-dependence projection digest;
- final v8 digest.

Validation recomputes v7 truth and dependence state from live canonical registries. Serialized v8 scope is not self-authenticating.

## Verification v8

A14 uses dedicated `DependenceTruthVerificationReceipt` and `DependenceTruthVerificationLedger`; v7 receipts cannot masquerade as v8.

A v8 receipt exact-binds:

- claim, verifier, channel, result;
- exact v8 scope/context/as-of;
- verification evidence IDs;
- verifier source-provenance projection digest;
- verifier source-dependence projection digest;
- v8 protocol/binding mode and canonical digest.

Receipt validity requires the accepted v7 provenance/temporal evidence checks plus current verifier dependence metadata. Missing/stale dependence metadata makes the receipt invalid for v8.

### Common-basis independence law

For each valid passing verifier:

1. derive the v5 provenance controller independence key;
2. reject independence credit if the key is missing or belongs to a decision-origin controller;
3. require current non-empty dependence bases;
4. reject independence credit if any verifier basis intersects any decision-source basis;
5. among remaining verifiers, form a graph where two receipts are connected when they share a provenance controller key or share at least one dependence basis;
6. collapse each connected component to one deterministic independence group;
7. `independent_source_count` is the number of surviving groups, not the number of receipts/controllers.

This is deliberately conservative and transitive: A shares basis X with B, B shares Y with C, so A/B/C form one dependence component even if A and C do not directly overlap.

Negative receipts remain retained. Correlation never deletes evidence or receipts; it only removes independence credit.

## Assurance v8

`DependenceTruthAssuranceGate` preserves all A13 epistemic, relation, temporal, undercutter, lineage, negative-verification and risk vetoes.

Additional v8 requirements:

- all sources in the v8 audit scope must have current dependence metadata for closure;
- invalid/stale verifier dependence blocks closure;
- risk thresholds remain LOW/STANDARD 1+1, HIGH 2+2, CRITICAL 3+3, but source count uses v8 dependence components;
- source dependence cannot increase verification credit; it can only preserve or collapse it.

`DependenceTruthClosureCertificate` exact-binds v8 scope, v8 verification projection, context/as-of, accepted receipt IDs, epistemic debt IDs, decision/reasons and canonical digest. Validation recomputes complete live v8 closure.

## Required regressions

A14 is not accepted without tests proving:

- two distinct controllers sharing one basis collapse to one independence group;
- three verifiers with transitive basis overlap collapse to one group;
- a verifier sharing a dependence basis with decision evidence receives zero independence credit even under a different controller;
- distinct controllers with disjoint bases remain independent;
- missing dependence metadata cannot mint v8 independence;
- verifier dependence revision stales receipt/coverage;
- relevant decision-source dependence revision stales scope/certificate;
- unrelated dependence revision does not stale target scope/certificate;
- v7 receipts cannot masquerade as v8;
- negative receipts remain retained;
- v7 behavior remains available unchanged;
- all A14 sidecars expose only `PARENT_COMPONENT_ID` and no `COMPONENT_ID`;
- restore rejects protocol, duplicate revision, sequence and predecessor attacks.

## Acceptance gates

1. RED proof on current accepted main.
2. GREEN focused A14 contracts.
3. Full Truth A suite on Python 3.11 and 3.13 with repository audit clean.
4. Freeze exact candidate head.
5. Compare intended Family-A diff only.
6. Current-main synthetic full Refoundation proof on Python 3.11 and 3.13.
7. Clean review surface and mergeability.
8. Expected-head production merge and exact merge-parent verification.
9. Separate documentation-only acceptance seal.
10. Fresh seal Truth A and full Refoundation proof, expected-head seal merge, final canonical verification.
