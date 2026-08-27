# Refoundation Wave 5AG: Native Evaluation Evidence

## Goal

Move semantic ownership of `evaluation.evidence` from the historical `cogcoder.organization.evaluation_evidence` implementation into `nolane.evaluation.evidence` without changing accepted behavior, while preserving exact historical import identity as a compatibility bridge.

## Starting authority

- Base: `refoundation/epoch0-wave5af-native-evaluation-regimes` at `9cbaed5d27a96c14b32e30f39ecfb31742272a5d`.
- `evaluation.regimes` is already canonical-native and is the canonical regime dependency for this cutover.
- `nolane.evaluation.evidence` is currently an Epoch-0 facade at `0.0.0` that reverse-imports the historical implementation.
- `evaluation.evidence` remains in active facade/native-debt state.
- Historical implementation behavior includes observation validation, deterministic digests, matched-budget comparison, organization-superiority assessment, ablation assessment, and state round-trip.

## Invariants

1. Preserve all accepted evaluation-evidence semantics exactly.
2. `nolane.evaluation.evidence` must own every evidence public type and `EvaluationEvidenceLedger` identity after cutover.
3. Canonical evidence code must not import `cogcoder.organization`.
4. Canonical dependencies must be used directly:
   - `.regimes` for regime/evaluation-mode authority.
   - `nolane.organization.identity.AgentRegistry` for identity authority.
   - `nolane.external_core.evidence.EvidenceRecord` for verification-evidence authority.
   - `nolane.core.canonical_digest.canonical_digest` for digest authority.
5. `cogcoder.organization.evaluation_evidence` becomes an exact re-export bridge to canonical identities.
6. Component revision advances only `evaluation.evidence`, from `0.0.0` to `0.0.1`.
7. Remove the active facade only after canonical ownership + bridge identity are established.
8. Add `evaluation.evidence` to the canonical-native implementation ledger before retiring its debt.
9. Generated `CURRENT/*` projections must reflect source-of-truth changes; do not invent independent authority in generated files.
10. Previous Wave 5AF assertions must remain monotonic: accepted prior components stay canonical-native and debt can only decrease.

## TDD sequence

### 1. RED contract

Add `tests/test_refoundation_wave5ag_native_evaluation_evidence.py` that requires:

- canonical metadata/version/migration identity;
- canonical ownership of `EvaluationObservation`, `MatchedBudgetComparison`, `OrganizationSuperiorityAssessment`, `AblationAssessment`, and `EvaluationEvidenceLedger`;
- exact legacy-to-canonical public identity bridging;
- zero reverse imports to `cogcoder.organization` from the canonical module;
- direct canonical dependency imports;
- representative observation/state/digest round-trip and matched-budget behavior;
- implementation ledger = `CANONICAL_NATIVE`;
- active facade removed;
- native debt excludes `evaluation.evidence` and decreases from 17 to 16;
- current status records Wave 5AG and 16 non-native boundaries.

Confirm this contract fails against the starting facade state for the intended ownership/version/debt reasons.

### 2. Semantic migration

Replace the `nolane.evaluation.evidence` facade with the full accepted historical implementation. Change only dependency imports and canonical metadata needed for ownership. Do not opportunistically rewrite algorithms in the same cutover.

### 3. Historical bridge

Replace `cogcoder.organization.evaluation_evidence` implementation with a compatibility module that re-exports the canonical evidence public API exactly.

### 4. Authority/version/facade cutover

- Advance `evaluation.evidence` component revision to 1.
- Remove `evaluation.evidence` from active facade bindings.
- Register `evaluation.evidence` in the `_NATIVE` implementation authority map with historical source provenance.

### 5. Projection and acceptance

Materialize/refesh native debt and readable `CURRENT` projections using the repository's authoritative projection procedure. Preserve previous acceptance oracles as monotonic ceilings rather than exact stale counts when needed.

### 6. Verification

Run, in increasing scope:

1. Wave 5AG contract.
2. Existing evaluation evidence tests and Wave 5AF contract.
3. Refoundation/source-of-truth acceptance suites.
4. Full repository baseline through the repository CI/workflow surface available on the branch.

Do not record Wave 5AG as accepted until fresh verification is green.

## Non-goals

- No changes to evaluation stress/parameters/release/claims/scaling/campaign ownership in this wave.
- No semantic redesign of evaluation scoring or evidence policy.
- No cosmetic broad folder reorganization unrelated to an accepted ownership cutover.
- No changes to Assurance/Individual Evolution hidden reverse-coupling work in this wave.
