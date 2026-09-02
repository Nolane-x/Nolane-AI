# Truth / Knowledge A17 — Observation Fitness / Measurement Integrity Truth v11 — Production Acceptance

Status: **ACCEPTED / PRODUCTION**

Production merge: `220b72c24a53c7a26814314d1fbfef7615f3c70b`

Integrated candidate: `752cd9edd57e9db483a9db0bd7e43772c16dfff3`

Pre-A17 production base: `1a8160cc814eeb5ed894135fc03bf44c8c02e300`

Production tree: `56e5ed9834b986b889e453656c8b721a56dce79f`

Production PR: #332

Historical RED/TDD PR: #321

## Accepted boundary

A17 is an additive v11 Truth protocol beneath the existing five Family-A canonical authorities only:

1. `external.evidence`
2. `external.knowledge`
3. `external.epistemic`
4. `external.verification`
5. `external.assurance`

All five A17 helper modules expose their accepted `PARENT_COMPONENT_ID` and no `COMPONENT_ID`. A17 therefore adds no sixth Family-A authority.

Canonical v11 binding mode:

```text
fitness-observation-context-dependence-defeasible-justification-provenance-lineage-temporal-v11
```

## Accepted semantic law

A17 separates observation occurrence from epistemic usability.

> **OBSERVED is not equivalent to EPISTEMICALLY USABLE.**

Accepted invariants:

- an A16 `OBSERVED` result may still be epistemically unfit for the claim/use being judged;
- fitness is local and use-specific, never a global Evidence revocation;
- fitness state never changes Evidence polarity;
- the canonical fitness checks are exactly `CALIBRATION`, `INTEGRITY`, `RESOLUTION`, `SYNCHRONIZATION`, and `INTERFERENCE`;
- each check is categorical `PASS`, `FAIL`, or `UNKNOWN`; A17 introduces no scalar confidence;
- the target Evidence cannot self-certify its own fitness: fitness assessment requires distinct basis Evidence;
- a required unassessed, failed, indeterminate, or inactive-basis fitness condition can demote an otherwise supported target to `UNKNOWN`, never to `REFUTED` merely because fitness is deficient;
- fitness metadata never creates source/controller/common-basis independence;
- empty A17 fitness registries reproduce exact accepted A16/v10 epistemic, verification, and assurance behavior;
- relevant fitness-requirement, assessment, observation-result, or assessment-basis changes stale exact scopes, receipts, and certificates;
- unrelated fitness changes outside the target-lineage projection do not stale target state;
- v10 objects cannot masquerade as v11 objects;
- v11 Verification and Assurance reuse the accepted A16/v10 independence and risk-threshold algorithms rather than duplicating or weakening them.

## Accepted modules

### Knowledge

`nolane.external_core.knowledge_observation_fitness_truth`

- immutable `ObservationFitnessRequirementRevision` state;
- append-only `ObservationFitnessRequirementRegistry`;
- exact binding to A16 observation requirements and revision lineage;
- non-empty unique canonical fitness checks;
- relevant-only projection and strict restore/digest validation.

### Evidence

`nolane.external_core.evidence_observation_fitness_truth`

- categorical `FitnessCheckStatus` domain;
- `FitnessCheckAssessment` plus append-only `ObservationFitnessAssessmentRevision` / ledger;
- exact binding to an A17 fitness requirement and exact A16 `OBSERVED` result revision;
- complete required-check coverage;
- distinct non-empty assessment-basis Evidence;
- target Evidence self-certification rejected;
- non-`PASS` state requires an explicit reason;
- basis-Evidence liveness participates in the relevant projection so revocation stales dependent fitness truth.

### Epistemic

`nolane.external_core.epistemic_observation_fitness_truth`

- immutable v11 wrapper over the exact accepted A16/v10 `ObservationTruthScope`;
- fitness-requirement and assessment projection digests;
- explicit unassessed, failed, indeterminate, and inactive-basis fitness debt;
- if v10 supports a target and relevant fitness is not live-`PASS`, only that target becomes v11 `UNKNOWN`;
- underlying Evidence remains active and retains polarity;
- no fitness requirement preserves exact v10 semantics;
- live scope validation recomputes canonical state.

### Verification

`nolane.external_core.verification_observation_fitness_truth`

- dedicated v11 receipt/ledger/coverage domain;
- exact binding to v11 scope plus A16 observation and A17 fitness projections;
- relevant fitness requirement/assessment/basis mutation stales receipts;
- negative receipts remain retained;
- v11 receipts adapt into accepted A16/v10 verification logic so controller-root/common-basis independence is inherited exactly;
- fitness metadata cannot split a dependent verifier into independent corroboration;
- v10 binding-mode masquerading is rejected.

### Assurance

`nolane.external_core.assurance_observation_fitness_truth`

- dedicated v11 closure certificate/gate;
- live recomputation of v11 observation-fitness state;
- exact binding to observation and fitness projections plus v11 verification state;
- accepted A16 risk thresholds are inherited unchanged through the v10 assurance engine:
  - LOW/STANDARD → 1 independent verifier component + 1 channel;
  - HIGH → 2 independent verifier components + 2 channels;
  - CRITICAL → 3 independent verifier components + 3 channels;
- critical fitness debt or invalid live fitness prevents closure explicitly;
- relevant fitness changes stale certificates;
- cross-version and unexpected-field restore attacks fail closed.

## TDD / adversarial proof chain

A17 began with an intentional RED contract commit `c5f1d795e729d288e5e8fddcd7a7397f1315555a`.

Truth Knowledge A run `33519632593` established clean RED on Python 3.11: accepted A1–A16 compile passed and test collection failed at the intentionally absent A17 module with `ModuleNotFoundError: nolane.external_core.evidence_observation_fitness_truth`.

The implementation then added the five v11 sidecars, exact lineage/projection binding, strict restore behavior, target-self-certification rejection, v10 algorithm reuse, and Assurance closure semantics. The isolated A17 candidate reached GREEN in Truth Knowledge A run `33520695117` on Python 3.11 and 3.13 with direct A1–A17/v1–v11 compile, all Truth contracts, and repository authority audit.

Nolane World 0.12.0 was used only as an external adversarial reasoning/specification harness. Its evidence/provenance separation, hierarchy, calibration, missingness, observer-effect, independence, and fail-closed concerns were translated into repository contracts. Nolane World is not a canonical Nolane AI Truth authority.

## Clean latest-main integration

Concurrent specialists advanced non-A families while A17 was under construction. Before production integration, the then-current `main` was re-read as:

```text
1a8160cc814eeb5ed894135fc03bf44c8c02e300
  tree: dc2e527b95c65c021e889349db5fc44496a5a3a6
```

Comparison from the accepted A16 base found no overlap with any of the ten A17 paths. The exact isolated-GREEN A17 blobs were overlaid onto that current-main tree without recreating their contents.

Result:

- integrated candidate `752cd9edd57e9db483a9db0bd7e43772c16dfff3`;
- tree `56e5ed9834b986b889e453656c8b721a56dce79f`;
- parents preserve both the historical A17 line and then-current `main`;
- compare against base: behind 0 with exactly 10 intended paths;
- 5 production sidecars + 3 tests + Truth-A workflow + design specification;
- no B/C/D/E/F rollback.

## Merge-state full acceptance

Historical PR #321 synthetic merge was exactly:

```text
2c79007f39b6581ab428a53f2841eadcce05712f
  tree:        56e5ed9834b986b889e453656c8b721a56dce79f
  parent/base: 1a8160cc814eeb5ed894135fc03bf44c8c02e300
  head:        752cd9edd57e9db483a9db0bd7e43772c16dfff3
```

Truth Knowledge A PR run `33585353773` proved the synthetic merge on Python 3.11:

- direct A1–A17/v1–v11 compile: PASS;
- **308 Truth Knowledge tests passed**;
- repository audit: **173 historical artifacts; 173 moved / 0 quarantined; 0 with reference debt; 1 non-native component record**.

Full Refoundation Epoch 0 run `33585353712` was GREEN on Python 3.11 and 3.13 on the exact synthetic merge tree. The inspected Python 3.13 leg proved:

- **67/67 AI dossiers fresh** (134 derived files);
- repository audit fresh with 173 moved / 0 quarantined / 0 reference debt / 1 non-native component record;
- **730 Refoundation tests passed**;
- **308 Truth A tests passed**;
- zero-loss evidence generated and uploaded;
- **494 downstream organization/campaign/execution tests passed**;
- frozen Neural R2.3 contracts: **PASS**.

That is 1,532 passing pytest contracts in the inspected Python 3.13 integration leg, in addition to the audit and Neural verification.

Dedicated integration-head Truth push run `33585420769` then completed GREEN on both Python 3.11 and 3.13. Both jobs compiled canonical A plus A1–A17/v1–v11 sidecars, ran all Truth Knowledge contracts, and verified repository authority projections. The inspected Python 3.13 job proved **308 passed** and the same clean repository audit.

## PR replacement and race acceptance

Historical PR #321 intentionally remained a draft from its RED/TDD origin. The connected GitHub ready-for-review mutation failed on a connector GraphQL response-field bug (`fullDatabaseId`). A direct merge attempt was rejected fail-closed with HTTP 405 because the PR was still a draft. No production state changed.

Before replacement, PR #321 had:

- 0 comments;
- 0 reviews;
- no review-state debt to migrate.

PR #321 was closed as the historical RED/TDD record. Production replacement PR #332 was then opened non-draft from the exact same head `752cd9edd57e9db483a9db0bd7e43772c16dfff3`.

PR #332 was:

- `draft=false`;
- `mergeable=true` after GitHub recomputation;
- exactly 10 intended changed files;
- synthetic merge `fae1b3d7d13cb2873184bb6f7b50303fe562def0`;
- synthetic merge tree `56e5ed9834b986b889e453656c8b721a56dce79f`, byte-identical to the already verified integration tree.

The final race guard confirmed `main` remained exact base `1a8160cc814eeb5ed894135fc03bf44c8c02e300`. Production merge used expected-head protection against exact candidate `752cd9edd57e9db483a9db0bd7e43772c16dfff3`.

GitHub produced verified production merge:

```text
220b72c24a53c7a26814314d1fbfef7615f3c70b
  tree:   56e5ed9834b986b889e453656c8b721a56dce79f
  parent: 1a8160cc814eeb5ed894135fc03bf44c8c02e300
  parent: 752cd9edd57e9db483a9db0bd7e43772c16dfff3
```

The production merge tree is byte-identical to the verified candidate and merge-state trees.

Exact production-main push verification also completed:

- R1.9 Integrity run `33585788000`: **SUCCESS**;
- R2.0i Integrity run `33585788002`: **SUCCESS**.

## Final canonical statement

A17 Observation Fitness / Measurement Integrity Truth v11 is accepted in production.

Family A still has exactly five canonical authorities.

Observation occurrence and measurement fitness are separate epistemic facts.

Unfit or indeterminate required measurement state becomes explicit `UNKNOWN` debt rather than fabricated refutation, global Evidence revocation, or polarity change.

Fitness metadata never mints epistemic independence.

Serialized v11 state remains non-self-authenticating and must be recomputed against live canonical state.

Canonical Family-A status: **A1–A17 accepted**.
