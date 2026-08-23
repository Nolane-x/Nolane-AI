# Refoundation Epoch 0 Wave 5C — Native Memory Fabric Design

## Context

Wave 5B made `external.evidence` canonical-native. The next dependency-ordered component is `external.memory.fabric`, currently a compatibility facade at `nolane.memory.fabric` over `cogcoder.organization.memory` while its semantic record/enums (`MemoryScope`, `MemoryStatus`, `MemoryEntry`) still live in the mixed historical `cogcoder.organization.types` module.

Migrating only `MemoryFabric` while leaving its own schema authority historical would create a reverse dependency and a false-native surface. Wave 5C therefore migrates the complete smallest semantic unit for `external.memory.fabric`: its two enums, record schema, and store/visibility/promotion implementation.

## Decision

Canonical executable/schema authority becomes `nolane.memory.fabric` for:

- `MemoryScope`
- `MemoryStatus`
- `MemoryEntry`
- `MemoryFabric`

Historical import surfaces remain compatibility bridges and must resolve to the exact canonical objects:

- `cogcoder.organization.types.MemoryScope`
- `cogcoder.organization.types.MemoryStatus`
- `cogcoder.organization.types.MemoryEntry`
- `cogcoder.organization.memory.MemoryFabric`
- package-level `cogcoder.organization` exports where present.

## Non-goals

Wave 5C does not migrate:

- memory lifecycle receipts/relations;
- memory retrieval budgets/selection receipts;
- `core.canonical_digest`;
- context capsules/control plane;
- knowledge, skills, self-model, experience;
- execution/evaluation;
- historical archive artifacts.

## Zero-loss invariants

1. Preserve enum values exactly.
2. Preserve `MemoryEntry` field order, defaults, confidence validation, state serialization and restoration.
3. Preserve `MemoryFabric` write IDs/sequences, normalization, visibility rules, retrieval ordering, promotion rules, status mutation and state restoration.
4. Legacy imports preserve object/class identity (`is`).
5. Canonical `nolane.memory.fabric` contains no executable import from `cogcoder.organization.memory` or `cogcoder.organization.types` for the migrated symbols.
6. Only `external.memory.fabric` advances from `0.0.0` to `0.0.1` in this tranche.
7. `external.memory.fabric` becomes `canonical_native` with canonical write authority and is removed from active compatibility facades.
8. Native debt reduces exactly 43 → 42: `compatibility_facade` 31 → 30; `legacy_internal=4`, `historical_only=7`, `frozen_asset=1` remain unchanged.
9. `external.memory.lifecycle` and `external.memory.retrieval` remain compatibility facades.
10. No historical source path is deleted; legacy modules become bridges.
11. Repository-history quarantine remains fail-closed and unchanged unless independently proven safe.
12. All Wave 1–5B, 67-AI, zero-loss, organization/campaign/execution and frozen Neural R2.3 contracts remain green.

## Acceptance

Accept only on an exact head that passes the complete Refoundation workflow on Python 3.11 and 3.13, with repository audit freshness, zero-loss evidence artifacts, full regressions and frozen Neural metadata. The PR receipt must record exact head/run/artifact digests/debt delta and explicit no-deletion status.
