# Refoundation Epoch 0 — Wave 5K Native Knowledge Implementation Plan

> Execute with TDD and exact-head hosted verification. Do not merge automatically.

**Goal:** Move `external.knowledge` from historical-only debt into native canonical authority at `nolane.memory.knowledge` while preserving the dedicated R2 Knowledge behavior and quarantining R2.54 Cognitive Retrieval coupling outside this wave.

**Parent:** `c694e27c89c5c86c139271e97c51ff76110cb842`

**Branch:** `refoundation/epoch0-wave5k-native-knowledge`

## Task 1 — Freeze the forensic boundary

Sources:
- `cogcoder/knowledge_types.py`
- `cogcoder/knowledge_store.py`
- `cogcoder/knowledge_ledger.py`
- `cogcoder/knowledge_adapters.py`
- exclusion oracle: `cogcoder/r254_code_knowledge.py`

Verify that the dedicated four-file lineage contains the complete minimum semantic unit and that R2.54 imports Cognitive Retrieval / returns retrieval artifacts. Record this boundary in the design document. No production change in this task.

## Task 2 — Write the RED Wave 5K contract

Create:
- `tests/test_refoundation_wave5k_native_knowledge.py`

The test file must separate historical behavior oracles from desired architecture so that before implementation:
- historical deterministic behavior remains green;
- native ownership/version/provenance/debt assertions are red.

Required behavior coverage:
- document validation/trust bounds;
- deterministic chunk digest/ID and lexical+trigram retrieval;
- query/k validation;
- composite SHA dedup and deterministic ordering;
- ledger tamper/collision/idempotency/conflicts;
- bounded working-set semantics and insertion-order chunks;
- callback document/chunk normalization, tamper rejection, homogeneous-row contract;
- deterministic generic query anchors.

Required architecture coverage:
- `external.knowledge` becomes `CANONICAL_NATIVE` at `nolane.memory.knowledge`;
- version becomes `0.0.1` with write authority;
- exact legacy public-object bridges;
- no canonical executable import from `cogcoder.knowledge_*` or `cogcoder.r254_*`;
- four dedicated inventory destinations point to `nolane/memory/knowledge.py`;
- `r254_code_knowledge.py` is not claimed by that destination;
- conditional debt target is 34 with historical-only reduced by exactly one.

Run hosted RED from the exact RED head and inspect failing tests. Do not create production code until failure is shown to be the missing Wave 5K architecture rather than a broken historical oracle.

## Task 3 — Implement canonical Knowledge

Create:
- `nolane/memory/knowledge.py`

Implement the frozen semantic unit using the historical formulas/contracts without adding new semantics. Keep `trainable_parameter_count = 0` where historically defined. Preserve deterministic hashing, chunk boundaries, scoring and sorting exactly.

The canonical implementation must not import executable authority from historical Knowledge or R2.54/Cognitive Retrieval modules.

## Task 4 — Convert dedicated historical sources to exact bridges

Update:
- `cogcoder/knowledge_types.py`
- `cogcoder/knowledge_store.py`
- `cogcoder/knowledge_ledger.py`
- `cogcoder/knowledge_adapters.py`

Bridge public objects/functions to `nolane.memory.knowledge` so historical import paths preserve exact object identity. Preserve private helper availability if it is part of an existing import surface, but do not retain duplicate implementation authority.

Do not rewrite or re-home `cogcoder/r254_code_knowledge.py` in this wave.

## Task 5 — Advance Refoundation authority metadata

Update only the records required for `external.knowledge`:
- `cogcoder/refoundation/component_versions.py`
- `cogcoder/refoundation/implementation_status.py`
- inventory/provenance authority required by `GitSnapshotInventory`

Expected state, subject to audit proof:
- status: `CANONICAL_NATIVE`
- canonical module: `nolane.memory.knowledge`
- write authority: true
- component version: `0.0.1`
- legacy sources: the four dedicated Knowledge files

No R2.54 whole-file ownership claim.

## Task 6 — Generate official audit state

Use a temporary branch-scoped authority carrier only if direct generated-state update cannot be produced safely through ordinary repository tooling.

Carrier constraints:
- exact branch and exact expected parent gate;
- `fetch-depth: 0`;
- `PYTHONDONTWRITEBYTECODE=1`;
- run `python -m nolane.repository.audit --write` then `--check`;
- explicit staging whitelist only;
- fail closed on unexpected changes.

Never hand-edit generated debt.

Provisional expected debt after audit:
- compatibility facade 25
- legacy internal 2
- historical only 6
- frozen asset 1
- total 34

If generated audit disagrees, debug the semantic/accounting cause instead of forcing the number.

## Task 7 — GREEN and regression verification

Run targeted Wave 5K tests and relevant Knowledge/historical consumers first. Then run repository audit checks and the full hosted Refoundation workflow.

Acceptance requires both Python 3.11 and Python 3.13 success on the exact head.

## Task 8 — Remove temporary authority and prove cleanup

If a temporary carrier was created:
- delete it before acceptance;
- add `tests/test_refoundation_wave5k_bootstrap_cleanup.py` to assert it is absent;
- run the final full workflow again on the post-cleanup head.

No temporary workflow may survive acceptance.

## Task 9 — PR readiness

Create/update the Wave 5K pull request only after the exact clean post-cleanup head is fully green. Include:
- exact parent/base;
- exact accepted SHA;
- RED evidence;
- final Python 3.11/3.13 run IDs;
- audit/debt delta;
- R2.54 exclusion statement;
- zero deletion/move statement.

Mark Ready for Review only after acceptance. Do not merge.
