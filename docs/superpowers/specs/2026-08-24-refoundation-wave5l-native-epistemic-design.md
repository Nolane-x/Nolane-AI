# Refoundation Epoch 0 — Wave 5L Native Epistemic Design

## Parent acceptance
Wave 5L starts from exact hosted-green Wave 5K head `d1f5d67ec4305c974fb5cd1baa5c729ae6c8cabc`.

## Objective
Move implementation authority for `external.epistemic` from the historical R2.2 `cogcoder.epistemic_workspace` lineage into `nolane.external_core.epistemic` while preserving the locked R2.2 hypothesis/uncertainty behavior and keeping Causal, Experimentation, Cognitive Library, and R2.8 debugging outside this wave.

## Proven historical lineage
The dedicated R2.2 semantic unit is:
- `ClaimRecord`
- `Belief`
- `EpistemicConflict`
- `EpistemicWorkspace`

The accepted R2.2 behavior oracle is `tests/test_r22_epistemic_workspace.py`.

## Canonical dependency boundary
The canonical implementation accepts provenance-bound evidence-chunk shaped values through an internal structural protocol. This preserves the R2.2 behavior without reverse-importing `cogcoder.knowledge_types` or making Epistemic implementation authority depend on a historical Knowledge module.

The historical compatibility surface continues exposing `EvidenceChunk` from canonical Knowledge for source compatibility, but `EvidenceChunk` is not owned by Epistemic.

## Preserved behavior
Wave 5L preserves:
- SHA-256 fail-closed content provenance checks on ingest and verification;
- idempotent duplicate chunk ingest and collision rejection;
- claim parsing from `subject --relation--> object` evidence text;
- version-aware same-source supersession, including deterministic version token ordering;
- deterministic same-version tie-break by trust, score, then chunk id;
- independent-source corroboration;
- confidence from trust/score weighted support;
- contested-belief detection using configurable contest margin;
- alternatives and superseded evidence reporting;
- current conflict projection without erasing disagreement;
- narrow missing-query generation for unresolved or contested claims;
- original chunk-object retention and deterministic claim/current ordering where historically defined;
- zero trainable parameters.

## Compatibility and provenance
After cutover:
- `cogcoder.epistemic_workspace` becomes a compatibility bridge for `ClaimRecord`, `Belief`, `EpistemicConflict`, and `EpistemicWorkspace`;
- its legacy `EvidenceChunk` import remains available via canonical Knowledge;
- `external.epistemic` becomes `CANONICAL_NATIVE` with write authority;
- only `external.epistemic` advances from `0.0.0` to `0.0.1`;
- inventory pins `cogcoder/epistemic_workspace.py → nolane/external_core/epistemic.py`;
- no historical source is deleted or moved.

## Non-goals
No R2.8 repository-world-model/debugging extraction, Causal extraction, Experimentation extraction, Cognitive Library extraction, Knowledge redesign, Context cutover, planning/execution/evaluation work, or Neural change occurs in Wave 5L.

## Expected debt delta
Wave 5K accepted debt:
- compatibility facade: 25
- legacy internal: 2
- historical only: 6
- frozen asset: 1
- total non-native: 34

Wave 5L target after proven cutover:
- compatibility facade: 25
- legacy internal: 2
- historical only: 5
- frozen asset: 1
- total non-native: 33

## Acceptance
One exact post-cleanup head must prove native object ownership, exact historical bridge identities, no executable historical reverse import, preserved R2.2 behavior, dedicated inventory provenance, deterministic debt 33, fresh repository audit, absence of temporary write carriers, and complete Python 3.11/3.13 Refoundation workflow success through zero-loss evidence, regressions, and frozen Neural R2.3 contracts.