# Refoundation Epoch 0 Wave 5AN — Native Assurance Cluster

## Goal

Retire exactly `external.assurance` from native debt by moving semantic ownership of the complete Assurance cluster from historical `cogcoder.organization` modules to canonical `nolane.external_core` modules without changing accepted behavior.

Target debt: **10 -> 9**.

## Semantic closure

This wave owns these three historical implementation modules as one component boundary:

- `cogcoder.organization.assurance`
- `cogcoder.organization.assurance_evidence`
- `cogcoder.organization.assurance_profiles`

Canonical owners:

- `nolane.external_core.assurance`
- `nolane.external_core.assurance_evidence`
- `nolane.external_core.assurance_profiles`

The component remains a single authority record: `external.assurance`.

## Dependency rule

Canonical Assurance code may depend only on canonical owners for artifacts, authority, events, evolution, organization identity/registry, verification, and canonical digest helpers. No canonical Assurance module may reverse-import `cogcoder.organization`.

## TDD sequence

1. Commit a RED Wave 5AN contract before production changes.
2. Observe hosted RED failures proving the pre-cutover state.
3. Migrate all three implementation modules zero-loss to `nolane.external_core`.
4. Replace all three historical modules with exact-object compatibility bridges.
5. Advance `external.assurance` component version `0.0.0 -> 0.0.1`.
6. Retire its active facade and mark the implementation ledger `CANONICAL_NATIVE` with canonical write authority.
7. Materialize repository-audit projections and update `CURRENT/STATUS.md`, reducing debt `10 -> 9`.
8. Update only stale historical acceptance oracles that incorrectly freeze predecessor debt/native sets; keep them monotonic.
9. Run full Refoundation contracts, broad organization/campaign/execution regressions, dossier freshness, repository audit freshness, and frozen Neural R2.3 verification on Python 3.11 and 3.13.
10. Remove any temporary write-enabled carrier/trigger before final acceptance; add a cleanup guard.
11. Run fresh exact-final CI on the clean head, then merge using an expected-head lock.

## Behavioral invariants

- Assurance decision/state receipts remain byte/digest compatible.
- Assurance evidence state round-trip remains exact.
- Historical imports preserve exact public object identity.
- Policy semantics, blocking/override semantics, verification authorization and routing semantics are unchanged.
- No unrelated component boundary is retired in this wave.

## Acceptance

Wave 5AN is complete only when:

- all three canonical modules own their public classes/functions;
- historical modules are bridge-only;
- canonical Assurance imports contain no `cogcoder.organization` dependency;
- `external.assurance` is version `0.0.1`, `CANONICAL_NATIVE`, and absent from active facades/debt;
- committed audit projections are fresh and report exactly 9 non-native records;
- `CURRENT/STATUS.md` records Wave 5AN;
- temporary migration workflows are absent;
- fresh exact-final CI is green on both Python 3.11 and 3.13.
