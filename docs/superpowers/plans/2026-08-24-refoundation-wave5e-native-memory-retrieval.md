# Refoundation Epoch 0 — Wave 5E Native Memory Retrieval Plan

## Goal
Native-cutover `external.memory.retrieval` as the next smallest provable migration unit after hosted-green Wave 5D, preserving deterministic selection behavior, historical import identity, provenance, zero-loss guarantees, and fail-closed receipt validation.

## Parent
Exact Wave 5D accepted head: `943554461c72e0f76b12aa2ed0780b89a16a60b0`.

## Execution sequence
1. Freeze the semantic unit: `MemoryRetrievalBudget`, `MemorySelectionReceipt`, `MemoryRetrievalEngine`.
2. Add TDD RED contracts covering authority/version, legacy→canonical identity, reverse-import absence, budget validation, deterministic selection/scoring/drop reasons, relation influence, receipt/digest/state restoration, inventory provenance, and debt 40.
3. Prove hosted RED only fails on not-yet-cutover architecture/debt.
4. Move accepted implementation into `nolane.memory.retrieval` using canonical Fabric/Lifecycle dependencies; preserve shared `canonical_digest` debt only.
5. Turn `cogcoder.organization.memory_retrieval` into an exact compatibility bridge.
6. Remove only the retrieval facade, add canonical-native ledger/version/inventory provenance, and make prior tests forward-compatible without weakening parity.
7. Deterministically regenerate native debt; require archive index no-drift.
8. If a temporary write bootstrap is needed, scope it to the Wave-5E branch, make it fail-closed/idempotent/allowlisted, prove targeted GREEN, add a cleanup RED gate, then delete the bootstrap.
9. Run the complete exact-head Refoundation workflow on Python 3.11 and 3.13 through zero-loss evidence, full organization/campaign/execution regressions, and frozen Neural R2.3 checks.
10. Record exact head/run/artifact digests in the PR and mark Ready only when fully green. Do not merge automatically.

## Expected debt target
- compatibility facade: 28
- legacy internal: 4
- historical only: 7
- frozen asset: 1
- total non-native: 40

## Next dependency decision
After Wave 5E, do not automatically migrate Context. Reinspect the dependency graph and current implementation boundaries first; likely candidates include the remaining shared primitives (`core.canonical_digest`, `schemas.identity`) or knowledge/skills/experience/self-model foundations required before Context can be honestly native.
