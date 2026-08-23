# Nolane-AI Refoundation Epoch 0

Pinned source snapshot: `1a8f333f72dd02abacf1a1bd6e2288c1025521de`  
Canonical bootstrap version: `0.0.0`

This directory is the implementation home for the zero-loss repository refoundation.

## Non-negotiable rules

1. Exactly 67 permanent first-generation AI identities: 1 Central, 15 Regional Chiefs, 51 specialists.
2. Historical R/Part/evaluation evidence is immutable scientific history. A canonical component may cite `migrated_from`; it must not rewrite the historical label.
3. Component software versions use independent `0.0.N` revision lines. A change to one component does not mass-bump unrelated components.
4. `component_version`, `state_schema`, `neural_version`, `agent_definition_version`, evaluation-release version and Git SHA are separate identities.
5. Refoundation begins by adding compatibility contracts. Legacy runtime remains live until parity, state migration and rollback evidence exists.
6. No tracked path is deleted merely because it looks obsolete.
7. A destructive path action requires: full blob identity, `LINE_REVIEWED`, parity receipt, migration receipt and history provenance.
8. The destructive repository phase is blocked until census coverage is exactly 100% of tracked paths.
9. Foundry mechanisms may be preserved as bounded temporary work units, but no ephemeral worker becomes a 68th permanent AI identity.
10. Central override remains distinguishable from independent verification.
11. Execution-side security invariants remain at the final side-effect boundary: current lease, code-claim coverage, isolated workspace and authoritative neural checkpoint binding.
12. Passing unit tests is not enough to delete history; scientific evidence, state and authority parity must also survive.

## Wave 1 scope

Wave 1 adds only the foundation required to migrate safely:

- `cogcoder/refoundation/versioning.py` — component-local `0.0.N` revisions;
- `cogcoder/refoundation/manifests.py` — bootstrap agent/component manifests;
- `cogcoder/refoundation/composition.py` — pinned component graph and composition digest;
- `cogcoder/refoundation/migration.py` — fail-closed legacy path migration law;
- `cogcoder/refoundation/census.py` — whole-repository census coverage gate;
- `cogcoder/refoundation/compatibility.py` — exact blueprint↔manifest parity report;
- Refoundation-specific tests plus the full existing organization/campaign/execution regression suite.

No existing R/Part/organization source is deleted or semantically rewritten in this wave.

## Source-of-truth transition

Wave 1 intentionally uses the current accepted `build_first_generation_blueprint()` as the bootstrap source and proves field parity.

Later migration sequence:

```text
blueprint is authority
   ↓  Wave 1: derive canonical manifests + parity receipts
blueprint == manifests
   ↓  later wave: persist/lock manifests, dual-read and compare
manifests become authority, blueprint becomes generated compatibility facade
   ↓  after snapshot/import parity and rollback proof
legacy facade may be retired to history
```

This prevents a second writable identity truth from being introduced during the refactor.

## Refoundation completion is not Wave 1 completion

The whole repository refoundation remains blocked until:

- all tracked paths are censused;
- every active persisted schema has a migration/rollback story;
- one canonical plan revision authority is selected;
- one canonical lease epoch authority is selected;
- External Core fabrics are split by responsibility without losing provenance/privacy;
- historical runtime Part snapshots remain loadable or deterministically migratable;
- all 67 permanent AI personal lineages remain addressable by the same `agent_id`;
- scientific claims and accepted/rejected evidence remain reproducible.
