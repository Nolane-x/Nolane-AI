# Refoundation Epoch 0 — Wave 5D Native Memory Lifecycle Plan

## Goal
Native-cutover `external.memory.lifecycle` as the next smallest provable migration unit after hosted-green Wave 5C, preserving all historical imports, state semantics, provenance, zero-loss guarantees, and fail-closed behavior.

## Parent
Exact Wave 5C accepted head: `413ed507e7f7505b3f2a0b1e1f90e49189d9108c`.

## Execution sequence

1. **Forensic baseline**
   - Read the accepted historical lifecycle implementation, canonical facade, component specs, authority ledgers, inventory mappings, and lifecycle tests.
   - Freeze the semantic ownership set: `MemoryLifecycleReceipt`, `MemoryLifecycleLedger`, `MemoryRelationKind`, `MemoryRelation`, `MemoryRelationGraph`.

2. **TDD RED contracts**
   - Add `tests/test_refoundation_wave5d_native_memory_lifecycle.py`.
   - Require canonical-native status/write authority/version `0.0.1`.
   - Require exact legacy→canonical object identity for all five objects.
   - Require no reverse import to `cogcoder.organization.memory_lifecycle`.
   - Lock representative lifecycle/relation behavior, restore validation, fail-closed authorization and relation rebinding semantics.
   - Require retrieval to remain a facade.
   - Require target debt 41.
   - Run hosted RED and confirm only expected architecture/debt failures.

3. **Native implementation cutover**
   - Move the accepted implementation into `nolane.memory.lifecycle`.
   - Replace historical `cogcoder.organization.memory_lifecycle` implementation with a compatibility bridge to all five canonical objects.
   - Use canonical `AgentRegistry`, `EventLedger`, `MemoryFabric`, and `MemoryStatus` imports; retain the declared temporary `canonical_digest` shared-debt import only.

4. **Authority/provenance cutover**
   - Remove only `external.memory.lifecycle` from active facades.
   - Add it to the canonical-native implementation ledger.
   - Advance only its component revision to 1.
   - Add exact pinned inventory mapping `cogcoder/organization/memory_lifecycle.py → nolane/memory/lifecycle.py`.
   - Make prior Wave-5C tests forward-compatible where they freeze lifecycle debt/version state.

5. **Generated debt materialization**
   - Materialize `CURRENT/NATIVE_DEBT.json` and `.md` deterministically.
   - Assert `archive/INDEX.json` does not drift.
   - Target counts: compatibility facade 29, legacy internal 4, historical only 7, frozen asset 1, total 41.

6. **Bootstrap cleanup gate**
   - If a temporary contents-write bootstrap is required for deterministic multi-file surgery/materialization, make it branch-scoped, idempotent, fail-closed, and allowlist-only.
   - Add a RED acceptance assertion forbidding the bootstrap.
   - Delete it before final acceptance.

7. **Hosted acceptance**
   - Run complete Refoundation workflow on exact final head for Python 3.11 and 3.13.
   - Require compile, 67/67 dossiers, repository audit, all Refoundation contracts, zero-loss evidence generation/upload, full organization/campaign/execution regressions, and frozen Neural R2.3 metadata.
   - Capture run ID, evidence artifact IDs/digests, exact head, and debt delta in the PR.
   - Mark PR Ready only after both runtimes are fully green. Do not merge automatically.

## Explicit next tranche
After Wave 5D is accepted, inspect and, if still dependency-clean, proceed with a separate Wave 5E native cutover for `external.memory.retrieval`. Retrieval is deliberately excluded from Wave 5D so lifecycle parity can be proven independently.
