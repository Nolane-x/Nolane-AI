# Refoundation Epoch 0 Wave 5C — Execution Plan

## Task 1 — RED contracts

Add `tests/test_refoundation_wave5c_native_memory_fabric.py` proving the target end state before implementation:

- memory fabric is canonical-native, version `0.0.1`, writer true;
- active facade registry no longer contains `external.memory.fabric`;
- legacy enums/record/fabric resolve to canonical identity;
- canonical module has no reverse import to historical memory/types owners;
- enum/schema/fabric behavior and state round-trip remain compatible;
- lifecycle/retrieval remain facades;
- debt reduces exactly 43 → 42 with compatibility facades 31 → 30.

Confirm hosted RED fails only on intended cutover contracts.

## Task 2 — Native extraction

Replace `nolane/memory/fabric.py` facade with native definitions for `MemoryScope`, `MemoryStatus`, `MemoryEntry`, and `MemoryFabric`, preserving accepted behavior exactly.

Convert historical `cogcoder.organization.memory` into a compatibility bridge to canonical `MemoryFabric` and convert only the three migrated definitions in `cogcoder.organization.types` into canonical imports. Leave unrelated types untouched.

## Task 3 — Authority metadata

- bump `external.memory.fabric` local revision to 1;
- add canonical native owner to implementation ledger;
- remove `external.memory.fabric` from active facade bindings;
- keep lifecycle/retrieval at version 0.0.0 and compatibility-facade status;
- update wave-independent current-authority tests without freezing later-wave debt counts.

## Task 4 — Materialize debt

Run canonical repository audit writer, prove `archive/INDEX.json` does not drift, and materialize expected debt:

- compatibility_facade: 30
- legacy_internal: 4
- historical_only: 7
- frozen_asset: 1
- total non-native: 42

Any temporary write-enabled bootstrap used for deterministic large-file surgery must be removed before acceptance.

## Task 5 — Exact hosted acceptance

Require Python 3.11 and 3.13 complete success through compile, 67-AI freshness, repository audit, all Refoundation contracts, zero-loss evidence, organization/campaign/execution regressions and frozen Neural R2.3 metadata. Record exact acceptance evidence in the PR and mark Ready for review only after all gates pass.
