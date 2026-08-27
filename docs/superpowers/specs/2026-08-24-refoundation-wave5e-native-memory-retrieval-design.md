# Refoundation Epoch 0 — Wave 5E Native Memory Retrieval Design

## Status
Approved implementation tranche under the Refoundation Master Spec. This document does not supersede the Master Spec.

## Parent acceptance
Wave 5E starts from exact hosted-green Wave 5D head:

`943554461c72e0f76b12aa2ed0780b89a16a60b0`

Wave 5D established canonical authority for `external.memory.lifecycle`, reduced non-native debt to 41, preserved all historical paths, and passed the complete Python 3.11/3.13 Refoundation gate.

## Objective
Move implementation authority for `external.memory.retrieval` from `cogcoder.organization.memory_retrieval` to `nolane.memory.retrieval` while preserving historical import identity and all accepted selection/scoring/budget/receipt semantics.

The smallest complete semantic unit contains three public objects:

- `MemoryRetrievalBudget`
- `MemorySelectionReceipt`
- `MemoryRetrievalEngine`

Moving only the engine and budget would leave the canonical module dependent on historical ownership for its own selection receipt schema, so all three move together.

## Canonical dependency boundary
The native retrieval implementation must consume already accepted canonical owners:

- `MemoryFabric`, `MemoryEntry`, `MemoryStatus` from `nolane.memory.fabric`
- `MemoryRelationGraph` from `nolane.memory.lifecycle`

`canonical_digest` remains temporarily sourced from `cogcoder.organization.types`; this is explicit existing `core.canonical_digest` legacy-internal debt and is not broadened in Wave 5E.

## Preserved behavior
Wave 5E must preserve:

- positive retrieval-budget validation;
- selection receipt state/digest validation;
- deterministic estimated-unit calculation;
- visible-active memory filtering;
- task/tag/evidence/confidence/dependency/relation scoring;
- deterministic score ordering and tie-breaking;
- max-memory and estimated-unit budget enforcement;
- deterministic receipt identifiers;
- exact selected/dropped IDs and drop reasons;
- normalized tags;
- receipt lookup failure behavior;
- selected-entry projection;
- engine state/digest round-trip;
- restore validation against candidate memory IDs.

## Compatibility and provenance
After cutover:

- `cogcoder.organization.memory_retrieval` remains as a compatibility bridge exporting the exact three canonical objects;
- `external.memory.retrieval` leaves active facade debt and becomes `canonical_native` with canonical write authority;
- its component version advances `0.0.0 → 0.0.1` only;
- pinned-tree inventory preserves `cogcoder/organization/memory_retrieval.py → nolane/memory/retrieval.py` after facade retirement;
- no historical file is deleted or moved.

## Explicit non-goals
Wave 5E does not native-cutover context, knowledge, skills, experience, self-model, canonical digest, planning, execution, domains, evaluation, or Neural assets.

## Expected debt delta
Wave 5D accepted debt: compatibility facade 29, legacy internal 4, historical only 7, frozen asset 1, total 41.

Wave 5E target: compatibility facade **28**, legacy internal **4**, historical only **7**, frozen asset **1**, total **40**.

The sole intended debt reduction is `external.memory.retrieval` leaving `compatibility_facade`.

## Acceptance gates
Wave 5E is accepted only on one exact final head that proves canonical ownership of all three objects, exact historical bridge identity, no reverse import to the historical retrieval owner, preserved retrieval behavior/state semantics, exact inventory provenance, debt 40 with archive no-drift, no temporary write-enabled Wave-5E bootstrap, and complete Python 3.11/3.13 Refoundation workflow success through zero-loss evidence, full regressions, and frozen Neural R2.3 checks.
