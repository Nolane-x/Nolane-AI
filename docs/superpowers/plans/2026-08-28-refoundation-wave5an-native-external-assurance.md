# Refoundation Epoch 0 Wave 5AN — Native External Assurance Cluster

## Goal

Retire exactly the `external.assurance` compatibility boundary by moving the complete assurance semantic closure from historical `cogcoder.organization` executable ownership to canonical `nolane.external_core` ownership without changing accepted behavior.

## Semantic closure

The component is a three-module ownership cluster:

1. `cogcoder.organization.assurance` -> `nolane.external_core.assurance`
2. `cogcoder.organization.assurance_evidence` -> `nolane.external_core.assurance_evidence`
3. `cogcoder.organization.assurance_profiles` -> `nolane.external_core.assurance_profiles`

The helper modules are part of the component because the control plane directly depends on their schema, evidence-ledger and routing authority. A facade-only move of `assurance.py` is not an accepted cutover.

## Canonical dependencies

The migrated cluster must depend only on accepted canonical authorities:

- artifacts -> `nolane.external_core.artifacts`
- authority graph -> `nolane.organization.authority`
- events -> `nolane.organization.events`
- skills/evolution -> `nolane.memory.skills`
- identity registry -> `nolane.organization.identity`
- digest -> `nolane.core.canonical_digest`
- verification -> `nolane.external_core.verification`

No canonical Assurance module may import `cogcoder.organization`.

## TDD sequence

1. Commit a RED contract before production migration.
2. Observe hosted RED while the Wave 5AM baseline remains green.
3. Move the three implementations to canonical modules with component metadata on `nolane.external_core.assurance`.
4. Replace all three historical modules with exact-object compatibility bridges.
5. Advance `external.assurance` from `0.0.0` to `0.0.1`.
6. Retire the active facade and record `CANONICAL_NATIVE` implementation/write authority for the full three-module closure.
7. Update only stale global architecture oracles; preserve behavior contracts.
8. Materialize repository audit projections and reduce native debt exactly `10 -> 9`.
9. Add CURRENT Wave 5AN receipt.
10. Run compile, dossiers, audit, full Refoundation contracts, broad regressions and Neural R2.3 through a fail-closed hosted carrier if needed.
11. Remove any temporary write-enabled carrier/trigger before acceptance.
12. Run normal exact-final PR CI on the clean head.
13. Merge only with an exact expected-head SHA, then verify post-merge `main` and native debt.

## Public identity contract

Canonical ownership must include:

### assurance
- `AssuranceDisposition`
- `AssurancePolicy`
- `BlockingReceipt`
- `AssuranceDecision`
- `AssuranceOverrideReceipt`
- `PromotionAssuranceReceipt`
- `AssuranceControlPlane`

### assurance_evidence
- `ChallengeStatus`
- `AssuranceSubject`
- `ChallengeCase`
- `AssuranceEvidence`
- `AssuranceEvidenceLedger`

### assurance_profiles
- `AssuranceDomain`
- `AssuranceProfile`
- `AssuranceWorkRequest`
- `AssuranceCandidateScore`
- `AssuranceAssignmentReceipt`
- `AssuranceProfileRegistry`

All historical imports of these public objects must preserve exact Python object identity.

## Acceptance

Wave 5AN is accepted only when the clean exact-head PR merge candidate proves:

- canonical three-module ownership and exact historical bridges;
- no reverse historical imports;
- representative digest/state round-trip parity;
- component version `0.0.1`;
- `CANONICAL_NATIVE` + canonical write authority;
- no active `external.assurance` facade;
- repository audit fresh with exactly 9 non-native records;
- CURRENT Wave 5AN receipt;
- full Refoundation, broad regression and Neural R2.3 gates green on Python 3.11 and 3.13.
