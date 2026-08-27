# Refoundation Epoch 0 — Wave 5A Native Evidence Foundations

## Status

Approved continuation of the Maximum-Completeness Refoundation after the exact Wave-4 hosted-green head `5f45660acf8c7531719da7963d221da4e81249aa`.

Wave 5A is stacked on Wave 4. It does not require Wave 4 to be merged before development, but it must preserve the exact Wave-4 zero-loss and repository-quarantine contracts.

## Why this cohort

The Master Specification orders shared-substrate migration ahead of memory/context/domain/evaluation cutovers. Identity/authority/events and task/coordination/Central are already canonical-native, while `external.artifacts` and `external.verification` remain compatibility facades whose executable authority still lives under `cogcoder.organization.*`.

These two components form a bounded evidence-foundation cohort:

- `external.artifacts` owns content-addressed artifact records and deterministic artifact persistence;
- `external.verification` owns bounded candidate evaluation, promotion and rollback authority over the already-native identity/event primitives.

They can be extracted without pretending that the larger `core.canonical_digest`, `schemas.identity`, or `external.evidence` semantic boundaries are already native.

## Non-goals

Wave 5A does **not**:

- delete historical or legacy implementation files;
- extract the entire shared `cogcoder.organization.types` module;
- claim `core.canonical_digest`, `schemas.identity`, or `external.evidence` native;
- migrate memory, knowledge, skills, context, execution, domain systems or evaluation;
- change accepted runtime serialization;
- change the 67 permanent AI identities, authority graph, parameter accounting or Neural R2.3 assets;
- broaden verification claims beyond the existing bounded candidate/promotion contracts.

## Native extraction targets

### `external.artifacts` → `nolane.external_core.artifacts`

Canonical source must own:

- `ArtifactRecord`;
- `ArtifactStore`;
- deterministic canonical digest identity;
- sorted/deduplicated evidence references;
- canonical metadata JSON;
- idempotent duplicate insertion;
- exact `to_state` / `from_state` round-trip behavior.

Historical `cogcoder.organization.artifacts` becomes a compatibility bridge to the canonical classes. Legacy and canonical imports must resolve to the exact same class objects after cutover.

### `external.verification` → `nolane.external_core.verification`

Canonical source must own:

- `CandidateEvaluation`;
- `PromotionReceipt`;
- `RollbackReceipt`;
- `VerificationAuthority`;
- parameter-ceiling rejection;
- verification/false-accept/regression/missing-evidence rejection;
- accepted bounded-candidate receipts;
- promotion state and prior-version stack;
- exact rollback behavior;
- canonical event emission through the native EventLedger/AgentRegistry surfaces;
- exact state round-trip.

Historical `cogcoder.organization.verification` becomes a compatibility bridge to canonical class authority.

## Dependency direction

Allowed after cutover:

```text
nolane.external_core.artifacts
    -> shared schema/digest compatibility surface in cogcoder.organization.types (temporary declared debt)

nolane.external_core.verification
    -> nolane.organization.identity
    -> nolane.organization.events
    -> shared enum/parameter constants in cogcoder.organization.types (temporary declared debt)

cogcoder.organization.artifacts
    -> nolane.external_core.artifacts

cogcoder.organization.verification
    -> nolane.external_core.verification
```

Forbidden:

```text
nolane.external_core.artifacts -> cogcoder.organization.artifacts
nolane.external_core.verification -> cogcoder.organization.verification
```

The remaining shared-type dependency is explicit and does not authorize marking `core.canonical_digest`, `schemas.identity` or `external.evidence` native.

## Component versioning

Only the two extracted components advance:

- `external.artifacts`: `0.0.0` → `0.0.1`;
- `external.verification`: `0.0.0` → `0.0.1`.

All unrelated component versions remain unchanged.

## Implementation ledger rules

After acceptance:

- both components are `canonical_native`;
- both have `canonical_write_authority=true`;
- neither remains in `build_active_facade_bindings()`;
- the legacy source paths remain recorded as migration provenance;
- native debt decreases by exactly two records, from 46 to 44 on the Wave-4 parent state.

No other debt record may disappear as a side effect.

## Zero-loss contracts

Wave 5A must prove:

1. exact legacy→canonical public class identity;
2. canonical implementation modules do not import their historical implementation owners;
3. ArtifactStore deterministic identity, evidence ordering, metadata and state semantics are unchanged;
4. VerificationAuthority accept/reject, promotion, rollback, event and state semantics are unchanged;
5. exact migration destinations remain fail-closed in the snapshot census;
6. Wave-4 repository audit remains fresh and keeps historical bytes protected;
7. 67 AI profiles / 134 dossiers remain fresh;
8. all prior Refoundation, organization, campaign and execution regressions remain green;
9. frozen Neural R2.3 metadata remains unchanged;
10. no destructive deletion occurs.

## Acceptance

Wave 5A is accepted only when the exact branch head is hosted-green on Python 3.11 and 3.13 for the dedicated Refoundation workflow, including the new Wave-5 contracts and every protected Wave-1–4 regression.

A passing facade/import test alone is insufficient: class authority, state behavior, failure behavior, migration ledger status and prior-system regressions must all pass.