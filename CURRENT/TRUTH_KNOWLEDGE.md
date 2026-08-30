# Truth / Knowledge — External Core A

Status: **Refoundation A1–A8 accepted baseline. A10 Relation Semantics is acceptance-approved; its accepted status becomes effective only after expected-head merge and post-merge proof on `main`. A9 Temporal Validity remains a separate concurrent workstream and is not claimed by A10.**

## Canonical authority model

External Core family A remains exactly five canonical component authorities:

1. `external.evidence` → `nolane.external_core.evidence`
2. `external.knowledge` → `nolane.memory.knowledge`
3. `external.epistemic` → `nolane.external_core.epistemic`
4. `external.verification` → `nolane.external_core.verification`
5. `external.assurance` → `nolane.external_core.assurance`

Truth Closure is additive protocol semantics beneath those authorities. The helper modules `evidence_truth.py`, `knowledge_truth.py`, `epistemic_truth.py`, `verification_truth.py`, and `assurance_truth.py` must never declare `COMPONENT_ID`. `nolane.metadata.subprotocols` remains a metadata binding registry, not a sixth runtime component.

All Truth content identity uses `nolane.core.canonical_digest.canonical_digest`; no private digest authority is permitted.

## A1–A7 accepted baseline

The accepted baseline provides:

- immutable provenance-aware Evidence with source identity/family binding, polarity, channels, append-only revocation, anti-rebinding, anti-cross-subject laundering and tamper-evident restore;
- content-addressed Knowledge propositions with evidence references, derivation DAGs, topological restore, transitive invalidation and canonical set ordering;
- first-class Epistemic `UNKNOWN`, `SUPPORTED`, `REFUTED`, `CONTRADICTED`, competing propositions and epistemic debt;
- exact-state Verification receipts, live provenance validation, source-family independence, channel diversity and retained negative results;
- risk-sensitive Assurance, live canonical recomputation and non-self-authenticating closure certificates;
- bidirectional subprotocol ownership metadata without duplicate canonical authority;
- canonical ordering for set-semantic references.

A1–A7 deliberately used whole-ledger Knowledge/Evidence/Epistemic/Verification digests. That maximized invalidation safety but caused unrelated state changes to stale otherwise valid claim closures.

## A8 canonical dependency scope

A8 introduced `truth-dependency-scope-v2` under canonical `external.epistemic` Truth semantics. A `TruthDependencyScope` is a content-addressed state projection derived from live canonical Knowledge and Evidence; it is not caller-declared authority.

For target claim `T`, A8 scope is the fixed point of target lineage, every claim sharing `(subject, relation)` with a scoped claim, and every transitive parent of those competitors. This preserves target/ancestor conflict visibility while avoiding unrelated-ledger invalidation.

Global v1 and dependency-scope v2 remain historical compatibility modes. Their serialized payload identity is not rewritten by A10.

## A10 canonical relation semantics

A8 intentionally treated every same-`(subject, relation)` different-object claim as a potential competitor. That is safe but semantically over-conservative: `server --status--> online/offline` is usually exclusive, while `person --speaks--> English/French` may be simultaneously valid.

A10 gives this distinction to canonical `external.knowledge`, not to individual claims and not to a new authority.

`nolane.memory.knowledge` now owns:

- `RelationCardinality.EXCLUSIVE`;
- `RelationCardinality.MULTI_VALUED`;
- `RelationCardinality.UNSPECIFIED`;
- content-addressed `RelationSemanticsRevision` rows;
- append-only `RelationSemanticsRegistry` revision lineage;
- relevant-only relation-policy projection state/digest;
- additive `EvidenceLedger.semantic_conflicts()` while preserving historical `conflicts()` behavior.

Because the canonical Knowledge parent itself gains accepted API/semantics, `external.knowledge` advances from component revision `0.0.1` to `0.0.2`. The other four family-A parents remain at `0.0.1`. This is a parent implementation revision, not a subprotocol-registry revision.

### Relation revision law

For each relation:

- the first revision is exactly revision `1` and has no predecessor;
- every later revision increments by exactly one and binds the previous revision digest;
- same `(relation, revision)` semantic rebinding fails closed;
- missing policy resolves to `UNSPECIFIED` rather than silently assuming exclusivity or multiplicity;
- serialized duplicate/tampered revisions fail closed.

A claim cannot self-author relation cardinality. `KnowledgeClaim` remains unchanged and receives no relation-policy field.

## Relation-aware dependency scope v3

A10 adds a separate `TruthRelationAwareScope` / relation-aware scope v3. A8 v2 methods remain intact.

The v3 fixed point is policy-aware:

- `EXCLUSIVE`: supported sibling objects with the same `(subject, relation)` are competitors and enter the fixed point;
- `MULTI_VALUED`: distinct sibling objects coexist and are not competitors merely because their values differ;
- `UNSPECIFIED`: the competing neighborhood remains visible, but multiple supported values become explicit epistemic ambiguity debt instead of a fabricated contradiction.

Competitors admitted by the policy-aware neighborhood still bring their transitive parent lineage into the fixed point. Ancestor conflicts and ambiguity therefore remain visible to descendant closure.

A v3 scope binds:

- target claim;
- transitive target lineage;
- policy-aware fixed-point claim set;
- referenced evidence IDs;
- relevant relation IDs;
- scoped Knowledge digest;
- scoped Evidence digest;
- relevant relation-semantics projection digest;
- scoped epistemic assessments;
- relation-authorized contradictions;
- epistemic and relation-ambiguity debt;
- final canonical scope digest.

`EpistemicJudge.validate_relation_aware_scope()` re-derives the scope from live canonical Knowledge, Evidence and Relation Semantics and requires exact equality.

## Relation conflict and ambiguity law

For supported claims sharing a subject/relation with multiple object values:

- `EXCLUSIVE` → explicit `EpistemicContradiction` and competing-proposition debt;
- `MULTI_VALUED` → coexistence, with no contradiction solely from distinct objects;
- `UNSPECIFIED` → `relation_semantics_unspecified_for_multiple_values` debt.

Strict v3 Assurance blocks target ambiguity with `relation_semantics_ambiguous` and ancestor ambiguity with `relation_semantics_lineage_ambiguous`. Exclusive target/ancestor conflicts continue to use the established epistemic conflict vetoes.

## Verification binding modes

`TruthVerificationReceipt` remains one compatibility type with exact, non-interchangeable modes:

### Global v1

The historical payload binds whole Knowledge and Epistemic digests. No scoped-only fields are injected.

### Dependency-scope v2

`binding_mode = dependency-scope-v2` binds the exact A8 dependency scope. V2 selectors and projection digests consume only v2 receipts.

### Relation-aware scope v3

`binding_mode = relation-aware-scope-v3` binds the exact A10 relation-aware scope. V3 selectors and projection digests consume only v3 receipts.

V2 and v3 are never aliases. A v3 receipt cannot count as v2 coverage even when claim and scope strings happen to match; the inverse is also forbidden. Scoped serialized state cannot smuggle v1 global bindings.

Live provenance law remains unchanged: verification evidence must be active and must match claim, verifier identity, source family and channel. Negative receipts remain retained.

## Assurance binding modes

`TruthClosureCertificate` remains one compatibility type, but validation dispatch is exact by certificate mode.

- v1 re-derives the canonical global snapshot and v1 closure;
- v2 re-derives the canonical dependency scope and v2 closure;
- v3 requires canonical `RelationSemanticsRegistry`, re-derives the relation-aware scope and v3 closure.

`close_live()` selects the newest binding mode already established in target verification history. Once v3 history exists, relevant policy/state change cannot cause silent fallback to v2. Stale v3 receipts therefore fail closed rather than obtaining authority through a downgrade path.

A v3 certificate binds its exact relation-aware scope digest and exact v3 verification projection digest. It remains a decision receipt, not self-authenticating authority; `validate_certificate()` must re-derive it against live state.

## Relevant-policy invalidation law

Relation policy is projected only for relations actually inside the v3 scope.

Therefore:

- revising an unrelated relation does not stale the target scope/certificate;
- revising a relevant relation changes the relation-semantics projection and stales old v3 receipts/certificates;
- changing an exclusive relation to multi-valued, or the reverse, requires a new append-only relation revision rather than semantic rebinding of an existing revision.

## Serialization and compatibility law

- Set-semantic IDs remain sorted and unique before identity computation.
- V1 payloads do not gain v2/v3-only keys.
- V2 payloads retain their A8 byte semantics and cannot be reinterpreted as v3.
- V3 payloads cannot contain v1 global binding fields.
- Unknown/mixed binding modes fail closed.
- Duplicate serialized ledger/relation identities fail closed.
- Content-valid but semantically incomplete scope state still fails live canonical revalidation.
- Historical `EvidenceLedger.conflicts()` remains unchanged for compatibility; consumers that need cardinality-aware behavior call additive `semantic_conflicts()` with the canonical registry.

## Compatibility boundary

The existing canonical APIs remain authoritative for their established duties:

- `EvidenceRecord` for existing evidence/evaluation flows;
- `nolane.memory.knowledge` for reusable knowledge retrieval/provenance chunks and now canonical relation-semantics authority;
- `EpistemicWorkspace` for the accepted version-aware workspace;
- `VerificationAuthority` for bounded candidate evaluation/promotion/rollback;
- `AssuranceControlPlane` for policy/domain engineering and promotion assurance.

Truth Closure remains additive protocol semantics. A10 does not seize another family or introduce a sixth family-A authority.

## Hardening lineage

- **A1** — explicit Evidence → Knowledge → Epistemic → Verification → Assurance semantics.
- **A2** — canonical snapshots, parent-state propagation, competing-proposition retention, tamper-resistant restore.
- **A3** — evidence laundering, source-family rebinding, stale replay, forged state, ungrounded verification, legacy bypass and restore-order attacks.
- **A4** — duplicate-authority removal and canonical parent/helper binding.
- **A5** — certificate content integrity separated from live authority authenticity; duplicate serialization fails closed.
- **A6** — bidirectional subprotocol metadata binding without fake parent software revisions.
- **A7** — canonical set ordering / order-malleability closure.
- **A8** — fixed-point dependency-scoped state binding, unrelated-state stability, ancestor conflict/debt propagation and explicit v1/v2 compatibility.
- **A9** — reserved for the independent Temporal Validity workstream; A10 does not claim its status.
- **A10** — canonical relation-cardinality authority, relation-aware fixed-point v3, exact v1/v2/v3 mode separation and anti-downgrade Assurance.

## A10 acceptance gates

A10 becomes accepted only if an exact final candidate integrated with the then-current `main` passes:

1. Python 3.11 and 3.13 compile for canonical A authorities, Truth helpers and metadata/version authority;
2. every `tests/test_truth_knowledge_*.py` contract including A1–A10 adversarial/serialization tests;
3. repository authority projection audit with no duplicate authority or new migration debt;
4. full Refoundation Epoch 0 on Python 3.11 and 3.13, including 67/67 dossier freshness, repository audit, zero-loss evidence, organization/campaign/execution regressions and frozen Neural contracts;
5. PR scope/review verification showing only family-A/metadata/docs/tests changes and no unresolved blocking review thread;
6. expected-head merge followed by post-merge proof that `main` contains the tested candidate tree semantics.

Historical R-series workflows do not define current architecture authority.