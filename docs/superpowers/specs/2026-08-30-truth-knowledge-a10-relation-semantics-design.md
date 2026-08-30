# A10 — Canonical Relation Semantics

Status: approved design candidate for External Core family A.

## Problem

A1–A8 model a proposition as `(subject, relation, object)` and deliberately preserve multiple supported objects. However the accepted v1/v2 conflict rule treats every pair of supported claims sharing `(subject, relation)` but differing in `object` as competing. That is correct only when the relation is semantically exclusive. It produces false contradictions for valid multi-valued relations such as `speaks`, `capability`, or `member_of`.

A10 must make relation cardinality explicit without moving canonical ownership away from `external.knowledge`, without adding a sixth family-A authority, and without changing the exact historical serialization/identity of v1 or A8 v2 state.

## Authority boundary

Canonical relation semantics belong to `external.knowledge` because the semantics describe the proposition schema, not the current epistemic judgement. The canonical parent module remains `nolane.memory.knowledge` and gains an additive, append-only relation-semantics registry. The Truth helper `nolane.external_core.knowledge_truth` may consume that authority but may not declare a new `COMPONENT_ID`.

Because this wave adds accepted API/semantics to the canonical `external.knowledge` implementation itself, its software component revision may advance according to existing repository version rules. No other canonical component version changes merely because it consumes the new projection.

## Relation cardinality

`RelationCardinality` has exactly three states:

- `EXCLUSIVE`: distinct supported object values for the same `(subject, relation)` are mutually incompatible.
- `MULTI_VALUED`: distinct supported object values may coexist and are not competitors merely because their objects differ.
- `UNSPECIFIED`: no canonical cardinality authority has been established. Multiple simultaneously supported distinct values are an explicit epistemic ambiguity and strict canonical closure fails closed.

A claim cannot declare or override its own cardinality. Policy comes only from the canonical registry.

## Append-only revision lineage

A `RelationSemanticsRevision` is immutable and content-addressed. It binds:

- relation;
- positive integer revision number;
- cardinality;
- previous revision digest, empty only for revision 1;
- content digest.

`RelationSemanticsRegistry.record()` is append-only:

- first revision for a relation must be revision 1 with no predecessor;
- the next revision must be exactly current revision + 1;
- its predecessor digest must equal the exact current revision digest;
- same relation + revision may be re-recorded only if byte-semantically identical;
- same revision with different semantics fails closed;
- skipped, rollback, forked, or predecessor-rebound revision chains fail closed.

The registry preserves all revisions for audit. `current(relation)` returns the latest revision or `None`; absence means canonical `UNSPECIFIED`.

## Scoped relation projection

A10 adds a deterministic relation-semantics projection over only the relation names relevant to a target Truth scope. For each relation the projection contains either the exact current revision state or an explicit `unspecified` row. Its digest therefore changes when and only when the relevant canonical relation policy changes.

Consequences:

- changing policy for a relation used by target/ancestor/competitor lineage stales A10 verification/certificates;
- changing policy for an unrelated relation does not stale the target;
- registering a previously unspecified relevant relation changes the target scope identity;
- callers cannot supply an unverified relation policy projection as authority.

## Relation-aware fixed-point scope v3

A1–A7 global v1 and A8 dependency-scope v2 remain exact historical protocols. A10 adds `truth-dependency-scope-v3`.

For target `T`, start from the target plus every transitive parent. Repeatedly inspect each scoped claim according to the current canonical cardinality of its relation:

- `EXCLUSIVE`: add every claim with the same subject and relation but a different object, then add the full ancestry of each added competitor;
- `MULTI_VALUED`: do not add different-object claims merely because they share subject/relation;
- `UNSPECIFIED`: add every different-object claim and its ancestry so ambiguity cannot be hidden.

Repeat until the scope reaches a fixed point. The relevant relation set is the canonical sorted unique set of relations of all claims in the final scope.

The v3 scope binds:

- target claim ID;
- lineage claim IDs;
- fixed-point scope claim IDs;
- referenced evidence IDs;
- relevant relation IDs;
- scoped Knowledge digest;
- scoped Evidence digest;
- scoped Relation Semantics digest;
- scoped epistemic assessments;
- relation-aware contradictions;
- relation-aware epistemic debts;
- final content digest.

A supplied v3 scope is trusted only after live recomputation from canonical Knowledge, Evidence, and Relation Semantics authority.

## Relation-aware epistemic law

Per-claim support/refute assessment remains unchanged: cardinality does not alter whether evidence supports one claim.

Conflict grouping changes only in v3:

- for `EXCLUSIVE`, multiple supported distinct objects create `EpistemicContradiction` and `competing_supported_propositions` debt;
- for `MULTI_VALUED`, multiple supported distinct objects coexist with no contradiction/debt caused solely by cardinality;
- for `UNSPECIFIED`, multiple supported distinct objects create no fabricated contradiction but create explicit `relation_semantics_unspecified_for_multiple_values` debt on every affected claim.

Existing evidence-lineage debts, UNKNOWN/CONTRADICTED claim debts, target/ancestor critical-debt rules, and cross-subject evidence protections remain intact.

Strict v3 Assurance treats relation-semantics ambiguity on the target or any transitive ancestor as a non-criticality-dependent veto. This is schema uncertainty, not ordinary optional epistemic debt.

## Verification v3

`TruthVerificationReceipt` remains one compatibility type.

- v1 serialized payload stays unchanged.
- A8 `dependency-scope-v2` serialized payload stays unchanged.
- A10 adds `binding_mode = relation-aware-scope-v3`, bound only to the exact v3 scope digest plus existing evidence provenance fields.

V2 and v3 receipts must never be mixed when computing a projection. New helpers select only receipts of the exact requested binding mode. A stale v3 receipt remains retained for audit but contributes no current coverage.

Once a target has v3 verification history, live v3 closure must not fall back to v2 merely because all v3 receipts became stale after a relevant policy/state change.

## Assurance v3

`TruthClosureCertificate` also remains one compatibility type.

A v3 certificate binds:

- `binding_mode = relation-aware-scope-v3`;
- target/risk;
- exact v3 scope digest;
- exact v3 verification projection digest;
- accepted receipt IDs;
- lineage debt IDs;
- decision/reasons.

It excludes global v1 bindings and must not serialize as v2.

Strict v3 closure requires:

- live canonical v3 scope;
- supported target;
- no exclusive contradiction touching target/ancestor lineage;
- no relation-semantics ambiguity touching target/ancestor lineage;
- no existing target/ancestor critical-debt veto;
- provenance-valid v3 verification bound to the exact current v3 scope;
- no current-scope negative verification;
- existing risk-specific independent source-family/channel diversity.

`validate_certificate()` must recompute in the certificate's exact binding mode. A v3 certificate cannot validate without the canonical Relation Semantics registry used to recompute v3 state.

## Compatibility

A10 must not mutate A1–A8 historical identity:

- `KnowledgeClaim` state is unchanged;
- `EpistemicSnapshot` v1 is unchanged;
- `TruthDependencyScope` v2 is unchanged;
- global v1 receipt/certificate payloads are unchanged;
- dependency-scope-v2 receipt/certificate payloads are unchanged;
- old `close_live()` callers that do not provide relation semantics retain A8 mode selection exactly.

A10 is additive. Canonical relation-aware behavior is selected only through the explicit v3 authority path.

## Required adversarial contracts

A10 is not accepted unless tests prove all of the following:

1. `speaks=English` and `speaks=French` coexist under `MULTI_VALUED` without contradiction.
2. `status=online` and `status=offline` conflict under `EXCLUSIVE`.
3. the same pair under `UNSPECIFIED` yields explicit ambiguity debt and cannot strict-close.
4. claims cannot self-declare or override cardinality.
5. relation revision rebind, skip, rollback, fork, or wrong predecessor fails closed.
6. relation registry serialization is deterministic, duplicate-safe, chain-validated, and tamper-evident.
7. adding a valid multi-valued sibling does not stale an unrelated target member's v3 certificate.
8. adding an exclusive competitor changes scope and blocks/stales closure.
9. a relevant relation-policy revision changes v3 scope identity.
10. an unrelated relation-policy revision does not change v3 scope identity.
11. exclusive contradiction or unspecified-cardinality ambiguity on an ancestor propagates to descendant Assurance.
12. v1 and v2 serialized state remains exact historical semantics.
13. v3 receipts/certificates never mix with or fall back to v2 in order to evade current ambiguity/conflict.
14. live v3 scope/certificate validation recomputes canonical relation authority rather than trusting caller state.
15. repository authority remains exactly the accepted family-A authorities; no sixth component appears.
16. full Truth Knowledge and Refoundation Epoch 0 gates pass on Python 3.11 and 3.13 before merge.

## Out of scope

A10 does not add temporal validity, source trust scoring, ontology inference, relation synonymy, inverse relations, transitivity declarations, numerical constraints, or verification-polarity coherence. Those require separate adversarial waves and must not be smuggled into cardinality semantics.