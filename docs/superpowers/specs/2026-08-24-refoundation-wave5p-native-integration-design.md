# Refoundation Epoch 0 Wave 5P — Native Integration Design

## Status

Design freeze for the Wave 5P native Integration cutover. This wave starts from the accepted Wave 5O native Architecture branch and preserves the A1 repository-authority model, zero-loss historical compatibility, deterministic state semantics, and the accepted Part-IV Integration behavior.

## Objective

Move executable authority for `external.integration` from `cogcoder.organization.integration` into `nolane.external_core.integration` without redesigning Integration semantics.

The canonical invariant after this wave is:

> The complete executable Integration candidate graph/control-plane implementation lives in `nolane.external_core.integration`; `cogcoder.organization.integration` is provenance-compatible import history only.

Native-debt target: **30 -> 29**, removing only `external.integration`.

## Why Integration is the next boundary

Wave 5M established native Requirements authority, Wave 5N established native Planning authority, and Wave 5O established native Architecture authority. Integration is the next downstream authority in the accepted Requirements -> Planning -> Architecture -> Integration chain. It records implementation candidates against expected Architecture versions, compatibility assessments, verification evidence, dependencies, conflicts, and deterministic integration receipts.

Leaving Integration executable authority behind a reverse compatibility facade would keep the canonical semantic chain split across ownership eras. Wave 5P therefore closes the next ownership seam while leaving Compatibility/ADR/change-impact extraction for their own evidence-backed waves.

## Semantic boundary

Wave 5P owns these public objects:

- `ChangeCandidateStatus`
- `ChangeCandidate`
- `IntegrationReceipt`
- `IntegrationGraph`
- `IntegrationControlPlane`

It owns their accepted behavior:

- deterministic sorted candidate and receipt views;
- candidate identity and architecture-version validation;
- dependency existence and cycle rejection;
- topological integration ordering;
- exact graph/control-plane snapshot and restore semantics;
- write-authority checks for integration-state mutation;
- architecture component/interface reference validation on candidate admission;
- fail-closed integration acceptance when evidence is absent;
- fail-closed stale Architecture-version rejection;
- fail-closed compatibility rejection for unknown, breaking, or integration-unsafe assessments;
- verification-evidence gating;
- dependency-before-integration enforcement;
- conflict rejection against already integrated candidates;
- deterministic canonical receipt digest and monotonic receipt identifiers.

## Canonical dependency rule

The native module must use canonical dependencies where those dependencies already have native ownership. In particular, canonical digest authority comes from `nolane.core.canonical_digest`.

`CompatibilityAssessment` and `CompatibilityClass` may continue to use the accepted historical compatibility implementation until that semantic boundary receives its own native extraction. Wave 5P must not falsely claim native ownership of Compatibility.

The canonical Integration source must never import `cogcoder.organization.integration`.

## Historical bridge

After cutover, `cogcoder/organization/integration.py` becomes an explicit re-export bridge. Every public Integration object imported from the historical path must be the exact same Python object as the corresponding canonical object.

The historical module may not retain a second executable candidate graph/control-plane implementation and may not mutate authority independently.

## Version and implementation authority

After acceptance:

- component: `external.integration`;
- component version: `0.0.1`;
- implementation status: `canonical_native`;
- canonical module: `nolane.external_core.integration`;
- canonical write authority: `true`;
- provenance source: `cogcoder/organization/integration.py`;
- active facade entry: removed;
- generated native debt: 29.

No unrelated component version changes in this wave.

## Repository-authority synchronization

`CURRENT/STATUS.md` is current architecture authority and currently stops at Wave 4 even though accepted Refoundation implementation has advanced through Wave 5O. Wave 5P must repair that authority drift by recording the accepted Wave 5 lineage and current Wave 5P work without rewriting historical evidence.

This is documentation/authority synchronization only. It does not reinterpret the semantics of earlier waves.

## Persistence and compatibility

Wave 5P is an ownership migration, not a state-schema redesign. Existing `ChangeCandidate.to_state()` / `from_state()`, `IntegrationReceipt.to_state()` / `from_state()`, `IntegrationGraph.to_state()` / `from_state()`, and `IntegrationControlPlane.to_state()` / `from_state()` behavior remains semantically compatible.

Existing historical imports must remain loadable. Existing snapshots containing Integration state must restore through the canonical implementation without state rewriting or silent normalization.

## Explicit non-goals

Wave 5P does **not** redesign or migrate:

- Compatibility assessment ownership;
- ADR ownership;
- change-impact engines;
- lease/fencing authority;
- Requirements, Planning, or Architecture semantics;
- execution, coding, debugging, assurance, research, UI/UX, evaluation, or neural boundaries;
- historical archive placement or scientific evidence labels.

Those boundaries remain explicit debt until their own evidence-backed waves.

## Acceptance gates

Wave 5P is accepted only when all of the following hold on one exact source head:

1. TDD RED demonstrates pre-cutover canonical ownership/version/debt defects.
2. Every public Integration object is defined by `nolane.external_core.integration`.
3. Historical Integration imports are exact canonical object identities.
4. Canonical Integration has no reverse import of `cogcoder.organization.integration`.
5. Canonical Integration uses `nolane.core.canonical_digest`.
6. Existing candidate validation, DAG, ordering, snapshot/restore, evidence, compatibility, stale-architecture, dependency, conflict, write-authority and receipt semantics remain green.
7. `external.integration` is `canonical_native`, write-authoritative, and version `0.0.1`.
8. `external.integration` is absent from active facade bindings.
9. Repository audit regenerates native debt at exactly 29; generated truth is not hand-edited.
10. `CURRENT/STATUS.md` truthfully records accepted Wave 5M/5N/5O lineage and Wave 5P active work.
11. All `tests/test_refoundation_*.py` pass on Python 3.11 and 3.13.
12. Architecture/Integration Part-IV regressions and the broader organization/campaign/execution regression lane pass.
13. 67/67 dossier freshness and frozen Neural R2.3 metadata remain unchanged.
14. No temporary write-enabled carrier remains in the accepted source head.

No auto-merge is permitted.
