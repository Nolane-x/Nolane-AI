# Refoundation Epoch 0 Wave 5B — Execution Plan

## Task 1 — RED contracts

Add `tests/test_refoundation_wave5b_native_evidence.py` proving:

- `external.evidence` is still non-native before implementation;
- canonical module/class authority is required;
- legacy imports must bridge by class identity;
- component version must become `0.0.1`;
- behavior and state round-trip must remain unchanged;
- debt must reduce 44 → 43 with only `legacy_internal` changing 5 → 4.

Run hosted Refoundation CI and confirm failures are limited to the intended evidence-cutover contracts.

## Task 2 — Canonical extraction

Create `nolane/external_core/evidence.py` by moving only the accepted `EvidenceRecord` implementation. Do not add new evidence behavior.

In `cogcoder/organization/types.py`, import canonical `EvidenceRecord` and remove only the historical local class definition. Preserve all other schemas byte-for-byte where practical.

## Task 3 — Authority metadata

Advance `external.evidence` to component revision/version `0.0.1`. Register canonical native ownership in the implementation ledger. Update wave-independent acceptance sets to include the newly accepted native component.

## Task 4 — Materialized debt

Regenerate `CURRENT/NATIVE_DEBT.json` and `CURRENT/NATIVE_DEBT.md` with the canonical repository audit. Confirm archive index does not drift. Expected debt:

- `compatibility_facade`: 31
- `legacy_internal`: 4
- `historical_only`: 7
- `frozen_asset`: 1
- total: 43

## Task 5 — Hosted acceptance

On the exact final head, require Python 3.11 and 3.13 to pass compile, AI dossier freshness, repository audit, all Refoundation contracts, zero-loss evidence, organization/campaign/execution regressions, and frozen Neural R2.3 metadata.

Record the exact head SHA, run ID, evidence artifact digests and debt delta in the PR before marking it ready for review.
