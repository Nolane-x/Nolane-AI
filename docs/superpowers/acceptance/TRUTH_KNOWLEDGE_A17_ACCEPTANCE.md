# Truth / Knowledge A17 — Observation Fitness / Measurement Integrity Truth v11 — Production Acceptance

Status: **ACCEPTED / PRODUCTION**

Production merge: `220b72c24a53c7a26814314d1fbfef7615f3c70b`

Verified A17 head: `752cd9edd57e9db483a9db0bd7e43772c16dfff3`

Pre-A17 production base: `1a8160cc814eeb5ed894135fc03bf44c8c02e300`

Production tree: `56e5ed9834b986b889e453656c8b721a56dce79f`

Synthetic merge proof: `2c79007f39b6581ab428a53f2841eadcce05712f`

Production PR: #332

Historical RED/TDD PR: #321

## Accepted boundary

A17 is an additive v11 Truth protocol beneath the same five canonical Family-A authorities only:

1. `external.evidence`
2. `external.knowledge`
3. `external.epistemic`
4. `external.verification`
5. `external.assurance`

All five A17 modules expose `PARENT_COMPONENT_ID` and no `COMPONENT_ID`. A17 therefore does not mint a sixth Truth authority.

Canonical v11 binding mode:

```text
fitness-observation-context-dependence-defeasible-justification-provenance-lineage-temporal-v11
```

## Accepted semantic law

A16 established whether a required observation occurred. A17 closes the next gap: an observation may be present while still being unusable for the intended epistemic purpose.

Central law:

> **OBSERVED != EPISTEMICALLY USABLE.**

Accepted invariants:

- observation fitness is local and use-specific; it is not global Evidence revocation;
- canonical fitness checks are exactly `CALIBRATION`, `INTEGRITY`, `RESOLUTION`, `SYNCHRONIZATION`, and `INTERFERENCE`;
- canonical check states are `PASS`, `FAIL`, and `UNKNOWN`;
- A17 contains no scalar-confidence field or confidence laundering path;
- the target Evidence cannot self-certify its own fitness; assessment basis Evidence must be distinct;
- an unassessed, failed, indeterminate, or inactive-basis required fitness condition converts an otherwise supported target to `UNKNOWN`, never `REFUTED`;
- A17 never changes Evidence support/refute polarity and never globally revokes the observed Evidence;
- empty A17 fitness registries reproduce exact accepted A16/v10 epistemic semantics;
- fitness metadata does not create verifier independence;
- relevant fitness requirement, assessment, basis-Evidence, or observation-result mutation stales the bound v11 scope/receipt/certificate;
- unrelated fitness mutations outside the target lineage projection do not stale target state;
- v10/v11 protocol masquerading and unexpected/tampered restore state fail closed;
- v11 Verification reuses accepted A16/v10 independence logic rather than reimplementing a weaker variant;
- v11 Assurance reuses accepted A16/v10 risk thresholds: LOW/STANDARD 1+1, HIGH 2+2, CRITICAL 3+3.

## Accepted modules

### Knowledge

`nolane.external_core.knowledge_observation_fitness_truth`

- immutable `ObservationFitnessRequirementRevision`;
- append-only `ObservationFitnessRequirementRegistry`;
- exact A16 observation-requirement binding;
- exact nonempty unique fitness-check set;
- strict lineage, predecessor, sequence, digest, and restore validation;
- relevant-only target projection.

### Evidence

`nolane.external_core.evidence_observation_fitness_truth`

- `FitnessCheckStatus` and `FitnessCheckAssessment`;
- append-only `ObservationFitnessAssessmentRevision` / ledger;
- exact fitness-requirement and exact A16 observed-result binding;
- exact check coverage;
- distinct nonempty basis Evidence;
- target Evidence self-certification rejected;
- PASS/FAIL/UNKNOWN reason consistency;
- live basis-Evidence state included in relevant projection.

### Epistemic

`nolane.external_core.epistemic_observation_fitness_truth`

- immutable v11 wrapper over exact accepted A16/v10 `ObservationTruthScope`;
- exact fitness requirement/assessment projection binding;
- explicit unassessed, failed, indeterminate, inactive-basis, and combined unfit observation IDs;
- explicit critical fitness debt;
- v10-supported + required fitness debt -> v11 `UNKNOWN`, not `REFUTED`;
- live scope validation and exact target-lineage projection.

### Verification

`nolane.external_core.verification_observation_fitness_truth`

- dedicated v11 receipt/ledger/coverage domain;
- exact binding to v11 scope plus A16 observation and A17 fitness projections;
- live fitness-projection currentness checks;
- accepted A16 verification engine reused through a strict v10 adapter;
- controller-root/common-basis independence retained exactly;
- relevant fitness/basis mutation stales receipts;
- negative receipts retained;
- cross-version binding-mode masquerading rejected.

### Assurance

`nolane.external_core.assurance_observation_fitness_truth`

- dedicated v11 closure certificate/gate;
- exact binding to v11 scope, verification, observation and fitness projections;
- accepted A16 Assurance gate reused for risk thresholds and independence semantics;
- explicit fitness-invalid / critical-fitness-debt closure reasons;
- certificate validation rebuilds live canonical state;
- relevant fitness mutation stales certificates.

## TDD and integration proof chain

A17 began with an explicit RED contract. Truth Knowledge A run `33519632593` failed at the expected missing production module while the existing A1-A16 compile surface remained intact.

After implementation, isolated A17 Truth Knowledge A run `33520695117` was GREEN on Python 3.11 and 3.13.

Concurrent specialist work advanced `main`, so A17 was integrated onto exact then-current base `1a8160cc814eeb5ed894135fc03bf44c8c02e300` while preserving the exact A17 implementation blobs. The final verified head was:

```text
752cd9edd57e9db483a9db0bd7e43772c16dfff3
  tree: 56e5ed9834b986b889e453656c8b721a56dce79f
```

The PR synthetic merge was:

```text
2c79007f39b6581ab428a53f2841eadcce05712f
  tree:   56e5ed9834b986b889e453656c8b721a56dce79f
  parent: 1a8160cc814eeb5ed894135fc03bf44c8c02e300
  parent: 752cd9edd57e9db483a9db0bd7e43772c16dfff3
```

The synthetic merge tree is byte-identical to the final A17 head tree.

## Dedicated Truth-A acceptance

Truth Knowledge A run `33585353773` completed successfully on the exact synthetic merge state.

Both jobs were GREEN:

- Python 3.11: direct compile of canonical A + A1-A17/v1-v11 sidecars, **308/308 Truth tests passed**, repository authority audit fresh;
- Python 3.13: direct compile of canonical A + A1-A17/v1-v11 sidecars, **308/308 Truth tests passed**, repository authority audit fresh.

The fresh audit reported:

- 173 historical artifacts;
- 173 moved / 0 quarantined;
- 0 with reference debt;
- 1 non-native component record.

## Full Refoundation acceptance

Refoundation Epoch 0 run `33585353712` completed successfully on Python 3.11 and 3.13 on the same exact merge state.

The inspected Python 3.13 leg proved:

- canonical organization/refoundation/`nolane` compile PASS;
- **67/67 AI dossiers fresh** (134 derived files);
- repository audit fresh: 173 historical / 173 moved / 0 quarantined / 0 reference debt / 1 non-native component record;
- **730 Refoundation tests passed**;
- **308 Truth Knowledge A tests passed**;
- zero-loss evidence generation/upload PASS;
- **494 organization/campaign/execution regressions passed**;
- frozen Neural R2.3 contracts: **PASS**.

Python 3.11 completed the same Refoundation workflow successfully.

## PR and production merge

Historical draft PR #321 preserves the RED-to-GREEN development record. It was closed without merge only because the connected ready-for-review mutation failed at the connector response layer; its final verified head and proof were preserved unchanged.

Production replacement PR #332 used the same exact verified head, was non-draft, and merged on 2026-09-02.

GitHub produced verified production merge:

```text
220b72c24a53c7a26814314d1fbfef7615f3c70b
  tree:   56e5ed9834b986b889e453656c8b721a56dce79f
  parent: 1a8160cc814eeb5ed894135fc03bf44c8c02e300
  parent: 752cd9edd57e9db483a9db0bd7e43772c16dfff3
```

The production tree is byte-identical to the exact verified A17 tree.

## Final canonical statement

A17 Observation Fitness / Measurement Integrity Truth v11 is accepted in production.

Family A still has exactly five canonical authorities.

Observation presence and observation fitness are separate canonical facts.

Unfit or unassessed required observations create explicit epistemic UNKNOWN debt; they do not become negative Evidence and do not revoke the Evidence globally.

Serialized v11 state remains non-self-authenticating and must be recomputed against live canonical state.

Canonical Family-A status: **A1-A17 accepted**.
