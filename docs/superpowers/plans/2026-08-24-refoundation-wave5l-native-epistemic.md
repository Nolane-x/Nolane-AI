# Wave 5L Native Epistemic — Implementation Plan

> Execute with TDD, fail-closed authority changes, and exact-head hosted verification.

## Goal
Cut over `external.epistemic` from the dedicated R2.2 historical workspace to canonical `nolane.external_core.epistemic` without semantic expansion or zero-loss regressions.

## Task 1 — RED contracts
1. Add `tests/test_refoundation_wave5l_native_epistemic.py` before production code.
2. Reuse the R2.2 behavior oracle through historical imports so existing behavior remains green.
3. Add architecture assertions for status/version, canonical object identity, no historical reverse imports, dedicated inventory mapping, R2.8 exclusion, and debt 33.
4. Open a draft PR against Wave 5K and record hosted RED evidence. Expected failures must be architecture-only.

## Task 2 — Canonical implementation
1. Add `nolane/external_core/epistemic.py` with `ClaimRecord`, `Belief`, `EpistemicConflict`, `EpistemicWorkspace`.
2. Preserve R2.2 algorithms and error semantics.
3. Use a private structural provenance-chunk protocol; do not reverse-import historical modules.
4. Keep `trainable_parameter_count = 0`.

## Task 3 — Historical compatibility bridge
1. Replace `cogcoder/epistemic_workspace.py` implementation with exact object aliases to canonical Epistemic.
2. Preserve `EvidenceChunk` on the legacy module surface by importing it from canonical Knowledge.
3. Do not delete or move historical sources.

## Task 4 — Authority/provenance metadata
1. Advance only `external.epistemic` to component version `0.0.1`.
2. Move it from `_HISTORICAL_ONLY` to `_NATIVE` in implementation status.
3. Add only `cogcoder/epistemic_workspace.py → nolane/external_core/epistemic.py` to canonical native inventory destinations.
4. Keep R2.8/world-model/debugging files unmapped to Epistemic in this wave.

## Task 5 — GREEN and cross-wave repair
1. Run hosted Refoundation contracts.
2. Fix only root-cause parity/architecture regressions.
3. If older wave tests freeze global debt, change them to local/monotonic invariants; do not weaken their own accepted component assertions.

## Task 6 — Official audit materialization
1. Add a temporary branch-scoped fail-closed authority carrier only if direct generated-file materialization is otherwise unavailable.
2. Require exact expected parent/ancestry, `fetch-depth: 0`, `PYTHONDONTWRITEBYTECODE=1`.
3. Run `python -m nolane.repository.audit --write` then `--check`.
4. Stage only `archive/INDEX.json`, `CURRENT/NATIVE_DEBT.json`, `CURRENT/NATIVE_DEBT.md` when changed.
5. Commit generated outputs and remove the carrier.
6. Add/maintain cleanup test proving no temporary carrier remains.

## Task 7 — Exact clean-head acceptance
1. Trigger full Refoundation workflow on the post-cleanup head.
2. Require Python 3.11 and 3.13 success through compile, 67 dossier freshness, repository-audit freshness, Refoundation contracts, zero-loss evidence, regressions, and frozen Neural metadata.
3. Record exact head SHA/run/artifacts.
4. Only then mark the PR Ready for Review.
5. Never merge automatically.