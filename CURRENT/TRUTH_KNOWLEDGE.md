# Truth / Knowledge — External Core A

Status: **A1–A17 are accepted as the canonical External Core family-A Truth / Knowledge baseline. A17 Observation Fitness / Measurement Integrity Truth v11 was merged to `main` as `220b72c24a53c7a26814314d1fbfef7615f3c70b`.**

This document is the compact current architecture authority. The byte-identical A1–A15 authority that preceded A16 is preserved at `docs/superpowers/acceptance/TRUTH_KNOWLEDGE_A1_A15_HISTORY.md`. Detailed production evidence for the two latest layers is preserved at `docs/superpowers/acceptance/TRUTH_KNOWLEDGE_A16_ACCEPTANCE.md` and `docs/superpowers/acceptance/TRUTH_KNOWLEDGE_A17_ACCEPTANCE.md`.

## Canonical authority model

External Core family A remains exactly five canonical component authorities:

1. `external.evidence` → `nolane.external_core.evidence`
2. `external.knowledge` → `nolane.memory.knowledge`
3. `external.epistemic` → `nolane.external_core.epistemic`
4. `external.verification` → `nolane.external_core.verification`
5. `external.assurance` → `nolane.external_core.assurance`

Truth protocol modules are additive semantics beneath those authorities. Temporal, provenance, justification, undercutter, dependence, context, observation-completeness, and observation-fitness helpers expose only their accepted `PARENT_COMPONENT_ID`; none may mint a sixth `COMPONENT_ID`.

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
    ↓
fitness-observation-context-dependence-defeasible-justification-provenance-lineage-temporal-v11
```

Every version is an exact protocol domain. Historical scopes, receipts, registries, and certificates remain exact historical modes; an older object cannot silently masquerade as v11 or silently downgrade a v11 object.

## Accepted A1–A15 substrate

A16 and A17 inherit rather than replace all accepted A1–A15 semantics: immutable Evidence, content-addressed Knowledge, explicit epistemic UNKNOWN/SUPPORTED/REFUTED/CONTRADICTED state, dependency-local fixed points, relation cardinality, temporal applicability, provenance lineage, OR-of-AND justification, defeasible undercutters, source-dependence/common-basis collapse, context-qualified applicability, risk-sensitive live Verification/Assurance, and canonical live recomputation.

The complete A1–A15 current authority is preserved byte-for-byte in the historical document referenced above.

## Accepted A16 — Observation Completeness / Missingness Truth v10

A16 makes required observation opportunities first-class without treating missingness as Evidence.

Central A16 laws:

> **Absence of observed evidence is not evidence of absence.**

> **Missing, censored, unavailable, timed-out, or interfered required observations produce explicit incompleteness/UNKNOWN debt; they never silently become REFUTED Evidence.**

> **Observation identity, outcome, or context never creates epistemic independence.**

A16 adds five sidecars under the existing authorities:

- `knowledge_observation_truth.py` — immutable observation requirements and append-only requirement history;
- `evidence_observation_truth.py` — append-only `OBSERVED`, `MISSING`, `CENSORED`, `UNAVAILABLE`, `TIMEOUT`, and `INTERFERED` outcomes;
- `epistemic_observation_truth.py` — target-lineage completeness projection and explicit incompleteness debt;
- `verification_observation_truth.py` — v10 receipts binding exact observation projections while retaining A14/A15 independence logic;
- `assurance_observation_truth.py` — v10 live closure using accepted LOW/STANDARD, HIGH, and CRITICAL thresholds.

Only `OBSERVED` may bind exact existing Evidence. Observation results never mint Evidence. Non-observed outcomes remain incompleteness state, not support/refutation. Empty A16 state reproduces accepted v9 behavior.

A16 production acceptance is recorded in `docs/superpowers/acceptance/TRUTH_KNOWLEDGE_A16_ACCEPTANCE.md`.

## Accepted A17 — Observation Fitness / Measurement Integrity Truth v11

A17 closes the gap that remains after A16: an observation can be present while still being epistemically unusable for a particular claim/use.

Central A17 law:

> **OBSERVED ≠ EPISTEMICALLY USABLE.**

A17 fitness checks are categorical and exactly bounded to:

- `CALIBRATION`;
- `INTEGRITY`;
- `RESOLUTION`;
- `SYNCHRONIZATION`;
- `INTERFERENCE`.

Each check is `PASS`, `FAIL`, or `UNKNOWN`. There is no scalar-confidence field.

### Knowledge fitness requirements

`knowledge_observation_fitness_truth.py` belongs to `external.knowledge` and defines immutable, append-only fitness requirements that exact-bind A16 observation requirements and the required fitness-check set.

Requirements are lineage-bound, fail closed on sequence/predecessor/rebind/tamper errors, and project only fitness state relevant to the target lineage.

### Evidence fitness assessments

`evidence_observation_fitness_truth.py` belongs to `external.evidence` and records append-only fitness assessments for exact A16 `OBSERVED` results.

Assessment basis Evidence must be distinct and nonempty. Target Evidence cannot self-certify its own fitness. Non-PASS checks carry explicit reasons. Basis-Evidence live state participates in the canonical fitness projection.

Fitness state is local epistemic admissibility. A fitness failure does not globally revoke the underlying Evidence and does not alter its support/refute polarity.

### Fitness-aware Epistemic v11

`epistemic_observation_fitness_truth.py` belongs to `external.epistemic` and wraps the exact accepted A16/v10 scope.

For target-lineage observations with a current fitness requirement:

- no assessment → explicit unassessed fitness debt;
- inactive assessment basis → explicit inactive-basis debt;
- `FAIL` → explicit failed-fitness debt;
- `UNKNOWN` → explicit indeterminate-fitness debt.

If the exact v10 target would otherwise be `SUPPORTED`, any required fitness debt makes only that target `UNKNOWN`. It never becomes `REFUTED` through fitness state alone.

Empty A17 fitness registries preserve exact A16/v10 epistemic semantics.

### Verification v11

`verification_observation_fitness_truth.py` belongs to `external.verification` and exact-binds v11 scope plus A16 observation and A17 fitness projections.

The v11 ledger recomputes live fitness currentness and adapts valid v11 receipts into the accepted A16/v10 verification engine, preserving controller-root/common-basis independence semantics rather than duplicating or weakening them.

Relevant fitness requirement, assessment, basis-Evidence, or result changes stale receipts. Unrelated fitness mutations outside the target projection do not. Negative receipts remain retained. v10 binding modes cannot masquerade as v11.

### Assurance v11

`assurance_observation_fitness_truth.py` belongs to `external.assurance` and defines dedicated v11 certificates and live closure.

The v11 gate reuses accepted A16/v10 Assurance thresholds:

- LOW/STANDARD → 1 independent verifier component + 1 channel;
- HIGH → 2 independent verifier components + 2 channels;
- CRITICAL → 3 independent verifier components + 3 channels.

Required fitness debt or stale/invalid fitness verification blocks closure explicitly. Certificates exact-bind both observation and fitness projections and must validate against rebuilt live state.

## Compatibility and anti-laundering law

A16 and A17 are structurally additive:

- accepted `TruthEvidence` and `KnowledgeClaim` shapes are unchanged;
- v1–v10 protocol objects remain unchanged historical modes;
- empty A16 state reproduces accepted v9 behavior;
- empty A17 state reproduces accepted v10 behavior;
- all A16/A17 sidecars bind the existing five parents and expose no `COMPONENT_ID`;
- observation results cannot mint Evidence;
- non-observed outcomes cannot silently become negative Evidence;
- fitness failure cannot silently become negative Evidence or global Evidence revocation;
- observation or fitness metadata cannot mint controller/source/common-basis independence;
- the target Evidence cannot certify its own fitness;
- foreign-protocol, unexpected-field, projection-tampered, duplicate, revision-gap, predecessor, rebind, and cross-version restore attacks fail closed.

## A17 production acceptance proof

Historical RED proof: Truth Knowledge A run `33519632593` failed at the expected missing A17 production module while the accepted A1–A16 compile surface remained intact.

Isolated A17 GREEN: run `33520695117` passed Python 3.11 and 3.13.

Final integrated A17 head `752cd9edd57e9db483a9db0bd7e43772c16dfff3` was built on exact pre-A17 production base `1a8160cc814eeb5ed894135fc03bf44c8c02e300` with tree `56e5ed9834b986b889e453656c8b721a56dce79f`.

PR synthetic merge `2c79007f39b6581ab428a53f2841eadcce05712f` had the same exact tree.

Truth Knowledge A run `33585353773` was GREEN on Python 3.11 and 3.13. Each leg compiled canonical A plus A1–A17/v1–v11 sidecars, passed **308/308 Truth tests**, and passed the fresh repository authority audit.

Full Refoundation Epoch 0 run `33585353712` was GREEN on Python 3.11 and 3.13. The inspected Python 3.13 leg proved **67/67 dossiers fresh**, repository audit 173 historical / 173 moved / 0 quarantined / 0 reference debt / 1 non-native component record, **730 Refoundation tests**, **308 Truth-A tests**, **494 downstream organization/campaign/execution tests**, zero-loss evidence generation/upload, and frozen Neural R2.3 **PASS**.

Historical draft PR #321 preserves the RED/TDD development record. Production PR #332 merged the same exact verified head.

GitHub produced verified production merge `220b72c24a53c7a26814314d1fbfef7615f3c70b`, tree `56e5ed9834b986b889e453656c8b721a56dce79f`, with parents `1a8160cc814eeb5ed894135fc03bf44c8c02e300` and `752cd9edd57e9db483a9db0bd7e43772c16dfff3`.

Nolane World 0.12.0 was used only as an external adversarial reasoning harness. Transferred measurement-fitness, calibration, integrity, provenance, independence, and fail-closed invariants are encoded in repository contracts; Nolane World is not a canonical Nolane AI Truth authority.

Canonical Family-A status at this revision is therefore **A1–A17 accepted**.
