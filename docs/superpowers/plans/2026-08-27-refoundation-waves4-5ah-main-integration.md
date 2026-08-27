# Refoundation Waves 4–5AH Main Integration Gate

> **For agentic workers:** This receipt records the cumulative integration boundary after explicit user authorization to merge. It is not evidence of success by itself; the PR merge ref against `main` must pass fresh hosted verification before merge.

**Goal:** Integrate the accepted Refoundation lineage from Wave 4 through Wave 5AH into `main` without replaying stale RED-proof or abandoned side branches.

**Base:** `main` at `cb4194c2d9cea6c25340d4b74a0c0281c25bd502` (accepted Wave 3).

**Pre-integration accepted head:** `47fbd357c991d9e67b502841b956f3e560b8b6f2`.

**Ancestry invariant:** The accepted branch is a strict descendant of the exact current main merge base: 446 commits ahead and 0 behind before this receipt commit.

**Excluded side branches:** Stale/RED-proof-only branches are not integration authority, including PR #173 and PR #185.

## Required merge gate

Before merging the cumulative PR into `main`, the exact final PR head and its `main` merge candidate must pass on Python 3.11 and 3.13:

- namespace compilation;
- 67/67 AI resolved-dossier freshness;
- repository audit freshness directly from committed projections (`--check`, with no preceding self-healing `--write`);
- all `tests/test_refoundation_*.py` contracts;
- zero-loss evidence generation;
- all organization/campaign/execution regressions in the permanent Refoundation workflow;
- frozen Neural R2.3 metadata verification.

The expected current debt boundary is 15 non-native component records, with all 173 historical root artifacts still quarantined and 0 safe-to-move.

## Merge rule

Merge only after a fresh workflow run created after this integration receipt is committed and after PR #204 targets `main`. Use the exact final head SHA as the merge precondition. After merge, verify that `main` contains the merge and run/inspect post-merge gates before declaring integration complete.
