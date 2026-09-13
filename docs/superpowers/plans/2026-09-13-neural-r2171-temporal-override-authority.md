# Neural R2.17.1 Temporal Override Authority Implementation Plan

> **Execution status:** implementation and adversarial hardening are complete on the R2.17.1 branch; final exact-head acceptance and merge remain.

**Goal:** Bind Central override receipts to the exact block frontier that existed when they were issued so later same-artifact blocks make old receipts stale, including across serialization and restore.

**Architecture:** `OverrideReceipt` stores ordered same-artifact `block_frontier_ids` plus global `block_counter_at_issue`. `AuthorityBlock` reciprocally stores global `override_counter_at_record`. Restore validates each row and then proves the two append-only ledgers encode one common reachable block/override interleaving. `can_write()` requires the receipt frontier to equal the current frontier. Top-level authority state keys remain unchanged.

**Security boundary:** canonical structural reachability, not cryptographic authenticity. A party able to rewrite the entire mutually consistent history requires a trusted signature/MAC/external append-only provenance design; R2.17.1 does not claim that property.

**Base:** `main@2799fdc4d873eff0a644560e4c58a93f747ebd23`

## Task 1 — Original temporal authority RED

- Added live contracts for validity at issuance, same-artifact staleness, fresh reauthorization, and unrelated-artifact independence.
- Added serialized frontier, round-trip, malformed witness, stale-history, and version contracts.
- Later consolidated hosted evidence established the original temporal gap symmetrically on Python 3.11/3.13 before production repair.

## Task 2 — Frontier implementation and version boundary

- Added immutable `block_frontier_ids` to `OverrideReceipt`.
- Captured target-artifact block frontier in `central_override()`.
- Required exact current-frontier equality in `can_write()`.
- Added fail-closed restore validation for the frontier.
- Advanced public authority version to `0.0.2` and canonical implementation revision to `3` (`0.0.3`).
- Version-only RED was independently observed before the version cutover.

## Task 3 — One-sided issuance witness hardening

Adversarial review found that accepting a canonical historical frontier without proving issuance position was too weak. A stale receipt could be moved forward to the current frontier during restore.

- Test-only exploit head `b98af9e4a3693bde56aac5a43863327ec675c152`.
- Hosted run `34757618900`: Python 3.11 and 3.13 each `1 failed / 899 passed`; sole failure was the forward-binding exploit.
- Added `block_counter_at_issue` to `OverrideReceipt` and serialized override rows.
- Restore reconstructs the historical same-artifact frontier from global block sequence order and requires an exact match.

This closed simple forward binding but still left the issuance proof one-sided.

## Task 4 — Coordinated forward-binding RED

Threat-model review then tested a stronger forgery against an honest history `B1 -> O1 -> B2`:

- keep the honest stale snapshot restorable and unauthorized;
- jointly change `O1.block_counter_at_issue` from `1` to `2` and its frontier from `[B1]` to `[B1, B2]`;
- require restore to reject rather than revive `O1`.

Test-only head: `72f5dc71129fc0e92306f34a50485387137097e0`.
Synthetic merge: `cab32574bd83d727274d88a8cc598cf9163c68b3`.
Hosted Epoch 0 run `34759442022`:

- Python 3.11: `1 failed / 902 passed`.
- Python 3.13: `1 failed / 902 passed`.
- On both runtimes the only failure was `test_restore_rejects_coordinated_forward_binding_of_frontier_and_issue_counter`, proving the expected root cause without unrelated regressions.

## Task 5 — Reciprocal causal-order repair

Production repair head: `c691c396d1da3bfc422a6267820b7091c958254f`.
Synthetic merge: `41e1f16470440d7c5c6710ef3af17cd5d29e9795`.

Minimal repair:

- Add immutable `AuthorityBlock.override_counter_at_record` and serialize it in block rows.
- Stamp the current global override counter in `record_block()`.
- Keep `OverrideReceipt.block_counter_at_issue` as the reciprocal witness.
- Parse both ledgers completely before committing restored graph state.
- Require both cross-counter sequences to be monotonic.
- For each block `i`, require its stored override count to equal the number of overrides reciprocally proven to precede block `i`.
- For each override `j`, require its stored block count to equal the number of blocks reciprocally proven to precede override `j`.
- Reject any mismatch as inconsistent temporal causal order.
- Keep public `0.0.2` / implementation revision `3`; this is hardening inside the same unmerged release candidate.

Epoch 0 run `34759695274` on synthetic merge `41e1f164...` is GREEN on both supported runtimes:

- Python 3.11: `903 passed` Refoundation, `308 passed` Truth/Knowledge, `814 passed` organization/campaign/execution; Neural R2.3 metadata PASS.
- Python 3.13: `903 passed` Refoundation, `308 passed` Truth/Knowledge, `814 passed` organization/campaign/execution; Neural R2.3 metadata PASS.

External Core, Memory Learning Substrate, R1.9, R2.0i, R2.63 Full Repository Release Bundle, R2.64 Frontier Fairness Hotfix, R2.64.1 Full Repository Release Bundle, and R2.67.1 Replacement Evidence also reached GREEN on this production candidate while the remaining lineage jobs continued. The expected historical reds remained baseline-only.

## Task 6 — Final documentation, exact-head acceptance, review, merge

The spec and this plan are updated to the reciprocal design only after production GREEN. Their docs-only commits create a new candidate and therefore invalidate `c691c396...` as final-head evidence even though its behavior evidence remains relevant.

Acceptance checklist:

- Run/observe the complete PR workflow matrix on the final docs head and its current synthetic merge.
- Require Epoch 0 Python 3.11 and 3.13 to retain `903 / 308 / 814` GREEN counts.
- Require External Core/version discipline, Memory Learning Substrate, E Acting Transactional Runtime, R1.9, R2.0i, R2.63/R2.64/R2.64.1, and R2.67.1 Replacement Evidence GREEN.
- Permit only the four accepted predecessor frozen reds if unchanged: R2.62 Complementary Causal Program, R2.65 Full Repository Release Bundle, R2.66 Full Repository Release Bundle, R2.67.1 Full Repository Release Bundle.
- Verify the first-generation runtime fingerprint remains `90fbbb26ca1519d957c4507291bd503f7d0b1fbf8d1929924e83d9f3c6050ed3` through the Refoundation fingerprint contract.
- Review the final changed-file set and all code/test patches; inspect reviews and unresolved threads.
- Update PR evidence with final base/head/synthetic merge and RED→GREEN lineage.
- Recheck current `main`, PR head, and synthetic merge immediately before merge. If any moves, invalidate stale evidence and rerun the required gates.
- Merge with `expected_head_sha` only after the exact candidate is frozen.
- Verify the returned merge commit is current `main`, confirm public `0.0.2` and implementation revision `3`, and inspect post-merge checks before declaring completion.
