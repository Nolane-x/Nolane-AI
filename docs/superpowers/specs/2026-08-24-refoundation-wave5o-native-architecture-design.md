# Refoundation Epoch 0 Wave 5O — Native Architecture Design

## Status

Design freeze for the Wave 5O native Architecture cutover. This wave starts from the accepted Wave 5N Planning branch and preserves the A1 repository-authority model, zero-loss historical compatibility, deterministic state semantics, and the already accepted Part-IV Architecture behavior.

## Objective

Move executable authority for `external.architecture` from `cogcoder.organization.architecture` into `nolane.external_core.architecture` without redesigning Architecture semantics.

The canonical invariant after this wave is:

> The complete executable Architecture graph/control-plane implementation lives in `nolane.external_core.architecture`; `cogcoder.organization.architecture` is provenance-compatible import history only.

Native-debt target: **31 -> 30**, removing only `external.architecture`.

## Why Architecture is the next boundary

Wave 5M established native Requirements authority and Wave 5N established native Planning authority plus one plan-revision clock. Architecture is the next downstream semantic authority that records requirement references, plan references, component/interface contracts, dependency edges, and architecture revisions. Leaving that authority behind a reverse compatibility facade would keep the canonical Requirements -> Planning -> Architecture chain split across ownership eras.

This wave therefore finishes the ownership transition for Architecture before touching Integration, execution, coding, assurance, or evaluation.

## Semantic boundary

Wave 5O owns these public objects:

- `ComponentKind`
- `ComponentStatus`
- `EdgeKind`
- `InterfaceClass`
- `InterfaceStability`
- `ArchitectureComponent`
- `InterfaceContract`
- `ArchitectureEdge`
- `ArchitectureRevision`
- `ArchitectureGraph`
- `ArchitectureControlPlane`

It owns their accepted behavior:

- deterministic sorted component/interface/edge views;
- versioned append-only architecture revision history;
- canonical graph digesting;
- atomic copy-on-revision mutation;
- interface-producer and edge-endpoint validation;
- fail-closed `DEPENDS_ON` cycle rejection;
- exact graph snapshot/restore and revision-sequence validation;
- owner-gated architecture writes;
- worker architecture-concern emission without implicit graph mutation.

## Canonical dependency rule

The native module must use canonical dependencies where those dependencies already have native ownership. In particular, canonical digest authority comes from `nolane.core.canonical_digest`.

`EventKind` may continue to use the accepted shared historical schema object until its own schema ownership boundary is extracted; Wave 5O must not falsely claim ownership of the mixed historical types module.

The canonical Architecture source must never import `cogcoder.organization.architecture`.

## Historical bridge

After cutover, `cogcoder/organization/architecture.py` becomes an explicit re-export bridge. Every public Architecture object imported from the historical path must be the exact same Python object as the corresponding canonical object.

The historical module may not retain a second executable graph/control-plane implementation and may not mutate authority independently.

## Version and implementation authority

After acceptance:

- component: `external.architecture`;
- component version: `0.0.1`;
- implementation status: `canonical_native`;
- canonical module: `nolane.external_core.architecture`;
- canonical write authority: `true`;
- provenance source: `cogcoder/organization/architecture.py`;
- active facade entry: removed;
- generated native debt: 30.

No unrelated component version changes in this wave.

## Persistence and compatibility

Wave 5O is an ownership migration, not a state-schema redesign. Existing `ArchitectureGraph.to_state()` / `from_state()` and `ArchitectureControlPlane.to_state()` / `from_state()` bytes and validation rules remain semantically compatible.

Existing historical imports must remain loadable. Existing snapshots that contain Architecture state must restore through the canonical implementation without state rewriting or silent normalization.

## Explicit non-goals

Wave 5O does **not** redesign or migrate:

- `external.integration`;
- ADR ownership;
- change-impact or compatibility engines;
- lease/fencing authority;
- Requirements or Planning semantics;
- execution, coding, debugging, assurance, research, UI/UX, evaluation, or neural boundaries;
- historical archive placement or scientific evidence labels.

Those boundaries remain explicit debt until their own evidence-backed waves.

## Acceptance gates

Wave 5O is accepted only when all of the following hold on one exact source head:

1. TDD RED demonstrates pre-cutover canonical ownership/version/debt defects.
2. Every public Architecture object is defined by `nolane.external_core.architecture`.
3. Historical Architecture imports are exact canonical object identities.
4. Canonical Architecture has no reverse import of `cogcoder.organization.architecture`.
5. Existing graph mutation, cycle rejection, digest, snapshot/restore, owner-write and concern semantics remain green.
6. `external.architecture` is `canonical_native`, write-authoritative, and version `0.0.1`.
7. `external.architecture` is absent from active facade bindings.
8. Repository audit regenerates native debt at exactly 30; generated truth is not hand-edited.
9. All `tests/test_refoundation_*.py` pass on Python 3.11 and 3.13.
10. Architecture/Integration Part-IV regressions and the broader organization/campaign/execution regression lane pass.
11. 67/67 dossier freshness and frozen Neural R2.3 metadata remain unchanged.
12. No temporary write-enabled carrier remains in the accepted source head.

No auto-merge is permitted.