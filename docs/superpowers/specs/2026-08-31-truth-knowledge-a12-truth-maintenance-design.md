# External Core A12 — Truth Maintenance / Multiple Independent Justifications v6

Status: design candidate for implementation on top of accepted A1–A11.

## Problem

Accepted A1–A11 represents each `KnowledgeClaim` with one conjunction of `evidence_ids` and `parent_claim_ids`. The legacy epistemic path therefore invalidates the entire claim when any required evidence or parent becomes unavailable. That is correct for one proof path, but it cannot represent a proposition that has several genuinely alternative derivations.

A12 adds explicit truth-maintenance semantics without mutating historical claim identity or weakening A1–A11.

## Authority law

A12 introduces no sixth family-A authority.

- justification state is a sidecar of `external.knowledge`;
- v6 epistemic scope is a sidecar of `external.epistemic`;
- v6 receipts are a sidecar of `external.verification`;
- v6 closure certificates are a sidecar of `external.assurance`;
- provenance remains owned by accepted A11 `external.evidence` sidecar state.

Every A12 helper declares `PARENT_COMPONENT_ID` and must not declare `COMPONENT_ID`.

## Core truth-maintenance law

A justification is one conjunction:

```text
J = evidence_1 AND ... AND evidence_n AND parent_1 AND ... AND parent_m
```

A claim with several effective justifications is a disjunction:

```text
claim = J_legacy OR J_1 OR J_2 OR ...
```

The OR is only a liveness/derivation law. It never multiplies source independence, confidence, assurance credit, or verification count.

## Legacy compatibility

Every canonical `KnowledgeClaim` contributes one deterministic implicit legacy justification containing exactly its accepted `evidence_ids` and `parent_claim_ids`.

Explicit A12 justifications are additive. With no explicit justification rows, v6 must reproduce the accepted A11 proposition/temporal/provenance result.

A1–A11 protocols remain byte-for-byte historical modes and do not read A12 state.

## Explicit justification revisions

`KnowledgeJustificationRevision` binds:

- protocol domain;
- stable `justification_id`;
- exact `claim_id` and exact `KnowledgeClaim.content_digest`;
- revision number;
- exact predecessor digest;
- canonical evidence set;
- canonical parent-claim set;
- enabled/retired state;
- canonical revision digest.

Rules:

1. first revision is exactly 1 and has no predecessor;
2. later revisions advance exactly +1 and bind the exact current predecessor;
3. a justification lineage cannot rebind to another claim or another claim digest;
4. parent claims must exist in canonical Knowledge;
5. self-parenting and effective justification dependency cycles fail closed;
6. duplicate live basis for the same claim fails closed, including duplication of the implicit legacy basis;
7. serialized duplicate/gap/rollback/predecessor/domain attacks fail closed.

## Effective dependency graph

For each claim, effective parents are the union of parents in its implicit legacy basis and every enabled explicit basis. A12 lineage follows this graph recursively.

This does not mutate the base `KnowledgeClaim` DAG. It is a v6-only derivation projection.

Relation-aware temporal fixed-point discovery uses the A12 lineage for target and admitted competitors, while preserving A10 cardinality and A9 explicit temporal applicability.

## Justification evaluation

Each effective justification is evaluated independently at explicit `TemporalContext`:

- every parent in that basis must be temporally active and epistemically `SUPPORTED`;
- every evidence row in that basis must be active at the same `as_of` and must bind the exact claim as subject;
- any unavailable/mismatched member makes that path non-live, not the whole claim;
- a path with only SUPPORT evidence is supported;
- a path with only REFUTE evidence is refuted;
- a path containing both is contradicted;
- a path without supporting/refuting evidence is unknown.

Claim aggregation is fail-visible:

- any supported path plus any refuted/contradicted path => `CONTRADICTED`;
- otherwise at least one supported path => `SUPPORTED`;
- otherwise at least one contradicted path => `CONTRADICTED`;
- otherwise at least one refuted path => `REFUTED`;
- otherwise `UNKNOWN`.

Therefore OR semantics cannot hide contradictory proof paths.

## Dead-path audit

V6 scope records per-justification status and reason. Dead alternatives remain auditable but do not generate blocking epistemic debt when another clean support path survives. If all paths fail, the claim becomes `UNKNOWN` and normal target/lineage closure rules block authority.

## Projection/staleness law

V6 scope binds only relevant state:

- A12 fixed-point claim IDs;
- relevant base Knowledge state;
- relevant justification current revisions and implicit bases;
- relevant evidence state and temporal projection;
- relevant Knowledge temporal projection;
- relevant relation policy projection;
- relevant source-provenance projection;
- explicit temporal context;
- assessments, justification statuses, contradictions and debt.

A justification revision outside the fixed point must not stale a target. A relevant revision must stale and be recomputed.

## Provenance law

Source independence still precedes assurance scoring.

V6 distinguishes:

- all source IDs touched by relevant justification evidence, for provenance completeness/staleness;
- supporting source IDs that actually contribute to live support, for verifier-origin exclusion.

A verifier controlled by a supporting evidence root controller receives zero independence credit. A controller appearing only in a dead, non-contributing path does not poison otherwise independent verification.

## Verification v6

V6 uses a dedicated receipt type and exact binding mode:

```text
justification-provenance-lineage-temporal-v6
```

A v5 receipt cannot masquerade as v6 and v6 cannot downgrade to v5. Receipts bind exact v6 scope, context/as-of, verifier provenance projection, evidence IDs, channel and pass/fail result. Negative results remain retained.

## Assurance v6

Risk thresholds remain unchanged:

- LOW/STANDARD: 1 independent verifier controller + 1 channel;
- HIGH: 2 + 2;
- CRITICAL: 3 + 3.

Closure blocks unsupported/contradicted target, unsupported/contradicted lineage, relevant relation ambiguity, critical epistemic debt, incomplete source provenance, invalid/negative verification, or insufficient independent verifier/channel diversity.

Certificates are non-self-authenticating and live-recomputed from canonical state.

## Required proof cases

A12 is not accepted until tests prove at least:

1. no explicit rows preserves legacy A11 behavior;
2. one dead legacy path + one clean explicit path keeps the claim supported;
3. every path dead makes the claim unknown and closure fails;
4. conjunction inside one path is strict;
5. support and refute across alternative paths becomes contradicted;
6. duplicate basis cannot manufacture multiple justifications;
7. claim/digest rebinding, revision gap/predecessor and dependency cycle attacks fail closed;
8. restore is domain-separated and rejects duplicate serialized revisions;
9. unrelated justification revisions do not stale relevant projection;
10. relevant justification revisions do stale it;
11. v6 verifier independence excludes live supporting-source controllers;
12. dead-path source controllers do not become false origin exclusions;
13. v5/v6 binding modes cannot masquerade;
14. A12 modules introduce no canonical family-A authority.
