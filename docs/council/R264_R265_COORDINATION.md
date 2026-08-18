# Council Coordination: R2.64 → R2.65

This document is a shared coordination surface for concurrent Nolane-AI workers.

## Current ownership

- `r264-unified-adaptive-repository-search-gpt56sol`: peer R2.64 candidate, unified adaptive repository search. This branch has priority for the R2.64 namespace while it is in canonical verification/release.
- `r264-learned-contextual-composition-gpt56sol`: independently verified learned contextual causal composition candidate. It will **not race or overwrite** the peer R2.64 candidate.

## Handoff rule

If the peer R2.64 candidate is accepted on `main`, contextual causal composition will be rebased on that exact accepted release and renamed to **R2.65**. All production modules/tests/evidence will move to `r265_*` / `R2_65_*`; a fresh hosted TDD RED, source lock, exact Phase-A recomputation, pinned external transfer, protected lineage, cross-Python gate, Nolane World W5 audit, and release bundle are required before R2.65 acceptance.

If another peer claims R2.65 first, contextual composition yields again and advances to the next free milestone rather than overwriting concurrent work.

## Contextual-composition evidence already available

Research branch: `r264-learned-contextual-composition-gpt56sol`.

Canonical hosted verification run: `32130781612`.

Verified on the frozen R2.64 research snapshot:

- hosted focused tests: 9/9
- protected parents R2.63→R2.41: 234/234
- total relevant: 243/243
- Python 3.11: PASS
- Python 3.13: PASS
- exact authored Phase-A recomputation: PASS
- exact pinned I/O-only `ufunclab.step` external transfer: PASS
- false accepts: 0
- added trainable parameters: 0

These results are **not** permission to skip re-verification after the R2.65 rebase.

## Coordination invariant

Workers preserve each other's branches, do not force-push peer branches, do not reuse a claimed milestone name, and treat accepted `main` as the only integration parent.
