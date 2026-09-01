# Truth / Knowledge — External Core A

Status: **A1–A16 are accepted as the canonical External Core family-A Truth / Knowledge baseline. A16 Observation Completeness / Missingness Truth v10 was merged to `main` as `578d372e13c4f1925088c7f8b5a747db688008c0`.**

This document is the compact current architecture authority. The byte-identical A1–A15 current authority that preceded A16 is preserved at `docs/superpowers/acceptance/TRUTH_KNOWLEDGE_A1_A15_HISTORY.md`. A16's detailed production evidence is preserved at `docs/superpowers/acceptance/TRUTH_KNOWLEDGE_A16_ACCEPTANCE.md`.

## Canonical authority model

External Core family A remains exactly five canonical component authorities:

1. `external.evidence` → `nolane.external_core.evidence`
2. `external.knowledge` → `nolane.memory.knowledge`
3. `external.epistemic` → `nolane.external_core.epistemic`
4. `external.verification` → `nolane.external_core.verification`
5. `external.assurance` → `nolane.external_core.assurance`

Truth protocol modules are additive semantics beneath those authorities. Temporal, provenance, justification, undercutter, dependence, context, and observation-completeness helpers expose only their accepted `PARENT_COMPONENT_ID`; none may mint a sixth `COMPONENT_ID`.

All canonical Truth identity uses `nolane.core.canonical_digest.canonical_digest`.

## Accepted protocol progression

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
    ↓
dependence-defeasible-justification-provenance-lineage-temporal v8
    ↓
context-dependence-defeasible-justification-provenance-lineage-temporal v9
    ↓
observation-context-dependence-defeasible-justification-provenance-lineage-temporal v10
```

Every version is an exact protocol domain. Historical scopes, receipts, registries, and certificates remain exact historical modes; an older object cannot silently masquerade as v10 or silently downgrade a v10 object.

## Accepted A1–A15 substrate

A16 inherits rather than replaces all accepted A1–A15 semantics: immutable Evidence, content-addressed Knowledge, explicit epistemic UNKNOWN/SUPPORTED/REFUTED/CONTRADICTED state, dependency-local fixed points, relation cardinality, temporal applicability, provenance lineage, OR-of-AND justification, defeasible undercutters, source-dependence/common-basis collapse, context-qualified applicability, risk-sensitive live Verification/Assurance, and canonical live recomputation.

The complete A1–A15 current authority is preserved byte-for-byte in the historical document referenced above.

## Accepted A16 — Observation Completeness / Missingness Truth v10

A16 closes the observation-selection gap intentionally left open by v9. Before v10, a set of observed Evidence items could be individually authentic, temporally valid, context-correct, provenance-bound, defeasible, and independent while the system still lacked a canonical representation of required observations that never produced Evidence.

The central A16 laws are:

> **Absence of observed evidence is not evidence of absence.**

> **Missing, censored, unavailable, timed-out, or interfered required observations produce explicit incompleteness/UNKNOWN debt; they never silently become REFUTED Evidence.**

> **Observation identity, outcome, or context never creates epistemic independence.**

### Knowledge observation requirements

`knowledge_observation_truth.py` belongs to `external.knowledge` and defines immutable `ObservationRequirement`, append-only `ObservationRequirementSetRevision`, and `ObservationRequirementRegistry` state.

Requirements bind exact claim identity/content and channel expectations. Legacy claims with no A16 requirement set remain explicitly unconstrained for compatibility.

### Evidence observation results

`evidence_observation_truth.py` belongs to `external.evidence` and records append-only observation outcomes through `ObservationResultRevision` / `ObservationResultLedger`.

Canonical outcomes are `OBSERVED`, `MISSING`, `CENSORED`, `UNAVAILABLE`, `TIMEOUT`, and `INTERFERED`.

Only `OBSERVED` may bind an exact existing `TruthEvidence`. A result record never mints Evidence. Non-observed outcomes remain incomplete observation state and cannot become support or refutation by serialization convention.

### Observation-complete Epistemic v10

`epistemic_observation_truth.py` belongs to `external.epistemic`.

`ObservationEpistemicJudge` wraps the exact accepted v9 `ContextTruthScope` and evaluates observation completeness only across the target's exact supporting lineage. Relation competitors that exist only in the broader audit scope do not create artificial observation obligations for the target.

If v9 would support a target but a required observation is incomplete, v10 evaluates the target as `UNKNOWN`, emits explicit observation debt, and preserves the underlying v9 audit assessment rather than laundering incompleteness into refutation.

Unrelated observation revisions outside the target projection do not stale the target.

### Verification v10

`verification_observation_truth.py` belongs to `external.verification` and defines dedicated v10 receipts and coverage.

A v10 receipt exact-binds the v10 scope, TruthContext, TemporalContext, observation-requirement projection, observation-result projection, verification Evidence, Evidence context, verifier provenance, and verifier dependence state.

Controller-root/common-basis independence remains inherited from A14/A15. Observation IDs, result IDs, contexts, or channels cannot split one dependent source into independent corroboration.

Relevant requirement/result changes stale verification. Unrelated changes do not. Negative receipts remain retained. v9 receipts cannot masquerade as v10.

### Assurance v10

`assurance_observation_truth.py` belongs to `external.assurance` and defines `ObservationTruthClosureCertificate` plus `ObservationTruthAssuranceGate`.

The gate recomputes live v10 state and preserves accepted thresholds:

- LOW/STANDARD → 1 independent verifier component + 1 channel;
- HIGH → 2 independent verifier components + 2 channels;
- CRITICAL → 3 independent verifier components + 3 channels.

Required observation incompleteness blocks closure with explicit observation-completeness reasons. Relevant observation revisions stale certificates; unrelated revisions do not. Serialized certificates are never self-authenticating.

## Compatibility and anti-laundering law

A16 is structurally additive:

- accepted `TruthEvidence` and `KnowledgeClaim` shapes are unchanged;
- v1–v9 protocol objects remain unchanged historical modes;
- empty observation requirement/result registries reproduce accepted v9 epistemic, verification, and assurance behavior;
- all five A16 sidecars bind the existing five parents and expose no `COMPONENT_ID`;
- an `ObservationResult` cannot mint Evidence;
- non-observed outcomes cannot silently become negative Evidence;
- observation metadata cannot mint controller/source/common-basis independence;
- foreign-protocol, unexpected-field, projection-tampered, duplicate, revision-gap, predecessor, and cross-version restore attacks fail closed.

## A16 production acceptance proof

A16's final semantic candidate `ce12f346d33d6dd655a0c1de51e0ed60976df8ca` passed Truth Knowledge A run `33474245556` on Python 3.11 and 3.13, including direct A1–A16/v1–v10 compile, all Truth contracts, and repository authority audit.

Concurrent work advanced `main`, so the exact 18 intended A16 blobs were overlaid directly onto then-current `main` `45b90000da324924b9a3f3ca646eeeee66ecadac`. This produced one-parent integrated candidate `bb70bb41c89c4dea8df667daa9e2dd8532c50acd`, tree `a2b82557158cbeb588e0f6704fa53d1ace8b8f92`, ahead 1 / behind 0 with exactly 18 intended files.

PR #312 synthetic merge `dbc42862366d3ad69c75cf836384197df5ce0cb8` had the exact same tree `a2b82557158cbeb588e0f6704fa53d1ace8b8f92`. Full Refoundation Epoch 0 run `33481146330` passed on Python 3.11 and 3.13. The Python 3.11 leg proved 67/67 dossiers fresh, repository audit 173 historical artifacts / 173 moved / 0 quarantined / 0 reference debt / 1 non-native component record, 705 Refoundation tests, 291 Truth A tests, zero-loss evidence, 478 downstream tests, and Neural R2.3 PASS. Python 3.13 completed the same workflow successfully.

PR #312 had 0 reviews, 0 review threads, and 0 comments. The final race guard confirmed `main` remained exact base `45b90000da324924b9a3f3ca646eeeee66ecadac`; production merge used expected-head protection against exact candidate `bb70bb41c89c4dea8df667daa9e2dd8532c50acd`.

GitHub produced verified production merge `578d372e13c4f1925088c7f8b5a747db688008c0`, tree `a2b82557158cbeb588e0f6704fa53d1ace8b8f92`, with parents `45b90000da324924b9a3f3ca646eeeee66ecadac` and `bb70bb41c89c4dea8df667daa9e2dd8532c50acd`.

Nolane World 0.12.0 was used only as an external adversarial reasoning harness for missing-observation, partial-observation, observer-effect, independence, and fail-closed closure invariants. Nolane World is not a canonical Nolane AI Truth authority; transferred invariants are encoded in repository contracts.

Canonical Family-A status at this revision is therefore **A1–A16 accepted**.
