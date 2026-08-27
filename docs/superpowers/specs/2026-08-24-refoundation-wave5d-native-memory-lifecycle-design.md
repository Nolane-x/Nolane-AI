# Refoundation Epoch 0 — Wave 5D Native Memory Lifecycle Design

## Status
Approved implementation tranche under the Refoundation Master Spec. This document does not supersede the Master Spec.

## Parent acceptance
Wave 5D starts from exact hosted-green Wave 5C head:

`413ed507e7f7505b3f2a0b1e1f90e49189d9108c`

Wave 5C established canonical authority for `external.memory.fabric`, reduced non-native debt to 42, preserved all historical paths, and passed the complete Python 3.11/3.13 Refoundation gate.

## Objective
Move implementation authority for `external.memory.lifecycle` from `cogcoder.organization.memory_lifecycle` to `nolane.memory.lifecycle` without deleting the historical import surface or weakening any accepted lifecycle/relationship behavior.

The smallest complete semantic unit contains five public lifecycle primitives/classes:

- `MemoryLifecycleReceipt`
- `MemoryLifecycleLedger`
- `MemoryRelationKind`
- `MemoryRelation`
- `MemoryRelationGraph`

Moving only `MemoryLifecycleLedger` and `MemoryRelationGraph` would leave the canonical module dependent on historical ownership for its own receipt/relation schemas, so all five move together.

## Canonical dependency boundary
The native lifecycle implementation must consume already accepted canonical owners where they exist:

- `AgentRegistry` from `nolane.organization.identity`
- `EventLedger` from `nolane.organization.events`
- `MemoryFabric` and `MemoryStatus` from `nolane.memory.fabric`

`canonical_digest` remains temporarily sourced from `cogcoder.organization.types`. That dependency is explicitly existing `core.canonical_digest` legacy-internal debt and is not a justification for broadening Wave 5D into a mixed shared-types migration.

## Preserved behavioral contracts
Wave 5D must preserve accepted lifecycle/relation behavior, including deterministic receipt/relation identifiers and digests; Memory/Context-region authorization; Memory-Chief-only reactivation; explicit reason/evidence and corrective-reference requirements; mutation through `MemoryFabric`; restore validation against registry, memory state and event anchors; semantic-relation authorization; self-relation restrictions; idempotent same-evidence relations; fail-closed evidence rebinding; and duplicate-relation rejection on restore.

## Compatibility and provenance
After cutover:

- `cogcoder.organization.memory_lifecycle` remains present as a compatibility bridge exporting the exact canonical class objects;
- the active facade registry no longer owns `external.memory.lifecycle`;
- the implementation ledger marks it `canonical_native` with canonical write authority;
- component version advances only for `external.memory.lifecycle`: `0.0.0 → 0.0.1`;
- pinned-tree inventory retains `cogcoder/organization/memory_lifecycle.py → nolane/memory/lifecycle.py` after facade retirement;
- no historical file is deleted or moved.

## Explicit non-goals
Wave 5D does not native-cutover `external.memory.retrieval`, context, knowledge, skills, experience, self-model, `core.canonical_digest`, planning, execution, domains, or evaluation.

## Expected debt delta
Wave 5C accepted debt is 42: compatibility facade 30, legacy internal 4, historical only 7, frozen asset 1.

Wave 5D target is 41: compatibility facade **29**, legacy internal **4**, historical only **7**, frozen asset **1**. The only intended debt reduction is `external.memory.lifecycle` leaving `compatibility_facade`.

## Acceptance gates
Wave 5D is accepted only when one exact final head proves all five objects are canonically owned by `nolane.memory.lifecycle`; historical imports preserve exact identity; no reverse import to the historical lifecycle owner remains; lifecycle/relation behavior and state round trips pass; retrieval remains a facade; debt materializes to 41 with no archive-index drift; no temporary write-enabled Wave-5D bootstrap remains; and the complete Refoundation workflow succeeds on Python 3.11 and 3.13 through zero-loss evidence, regressions, and frozen Neural R2.3 checks.
