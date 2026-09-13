# Neural R2.17.1 Temporal Override Authority Implementation Plan

> **Execution status:** implemented on the R2.17.1 branch; this plan records the accepted TDD path and the adversarial review amendment discovered before merge.

**Goal:** Bind Central override receipts to the exact block frontier that existed when they were issued so later same-artifact blocks make old receipts stale, including across serialization and restore.

**Architecture:** `OverrideReceipt` stores both the ordered same-artifact `block_frontier_ids` and the existing global `block_counter_at_issue`. `central_override()` captures both. Restore reconstructs the exact historical same-artifact frontier from global block sequence order and requires the serialized frontier to match it exactly. `can_write()` requires the receipt frontier to equal the current frontier. Top-level authority state keys remain unchanged.

**Security boundary:** canonical structural temporal consistency, not cryptographic authenticity. A coordinated full-state rewrite into another mutually consistent reachable history requires a separate trusted provenance/signature design.

**Base:** `main@2799fdc4d873eff0a644560e4c58a93f747ebd23`

## Task 1 — Original temporal authority RED

- Added live contracts proving validity at issuance, same-artifact staleness, fresh reauthorization, and unrelated-artifact independence.
- Added serialized frontier, round-trip, missing/unknown/wrong-artifact/duplicate/reordered witness, stale-history, and version contracts.
- Hosted original test-only RED: run `34757171784`, Python 3.11 and 3.13 each `4 failed / 881 passed`.

## Task 2 — Initial temporal frontier implementation

- Added immutable `block_frontier_ids` to `OverrideReceipt`.
- Captured target-artifact block frontier in `central_override()`.
- Required exact current-frontier equality in `can_write()`.
- Added fail-closed restore validation for the frontier.
- Advanced public authority version to `0.0.2` and canonical implementation revision to `3` (`0.0.3`).

## Task 3 — Adversarial review amendment

Self-review found that accepting any canonical historical prefix during restore was too weak. A stale receipt could be serialized with its frontier changed forward to the current full frontier, reviving authority after restore.

TDD hardening sequence:

- Test-only exploit head `b98af9e4a3693bde56aac5a43863327ec675c152`.
- Hosted run `34757618900`: Python 3.11 and 3.13 each `1 failed / 899 passed`; sole failure was the forward-binding exploit not being rejected.
- Strengthened test-only head `b58e67b0e3287ffc56571757fa4dda66717a70ef` added direct issuance-counter and missing-witness contracts.
- Hosted run `34757853438`: Python 3.11 and 3.13 each `3 failed / 899 passed`, exactly the three intended temporal-witness failures.

Minimal repair:

- Add `block_counter_at_issue: int` to `OverrideReceipt` and serialized override rows.
- Pin the existing global block counter when issuing an override.
- Reject missing, non-canonical, or future issue counters on restore.
- Reconstruct the exact historical same-artifact frontier as canonical blocks whose global block sequence number is `<= block_counter_at_issue`.
- Require serialized `block_frontier_ids` to equal that reconstructed frontier exactly.
- Keep public `0.0.2` / implementation `0.0.3`; this is an intra-milestone correction, not another semantic release.

Production repair head: `45ef79773d3d8d81b8ee01611224bfe6f15e865b`.

## Task 4 — Production GREEN and acceptance

Refoundation Epoch 0 run `34758069271` on synthetic merge `f662f96f6f4adaf3aaa0478f744adc9c7b96d310` is GREEN on both supported runtimes:

- Python 3.11: `902 passed` Refoundation, `308 passed` Truth/Knowledge, `814 passed` organization/campaign/execution; Neural R2.3 metadata PASS.
- Python 3.13: `902 passed` Refoundation, `308 passed` Truth/Knowledge, `814 passed` organization/campaign/execution; Neural R2.3 metadata PASS.

Acceptance checklist:

- Verify final docs-only head reruns the exact-head matrix cleanly.
- Require External Core, Memory Learning Substrate, E Acting Transactional Runtime, R1.9, R2.0i, R2.63/R2.64/R2.64.1, and R2.67.1 Replacement Evidence GREEN.
- Permit only the four accepted predecessor frozen reds if unchanged: R2.62 Complementary Causal Program, R2.65 Full Repository Release Bundle, R2.66 Full Repository Release Bundle, R2.67.1 Full Repository Release Bundle.
- Review final changed-file set, code/test patches, reviews and unresolved threads.
- Recheck base/head/synthetic merge immediately before merge.
- Merge with `expected_head_sha`.
- Verify the returned merge commit is `main`, confirm public `0.0.2` and canonical implementation revision `3`, and inspect post-merge push checks before declaring completion.
