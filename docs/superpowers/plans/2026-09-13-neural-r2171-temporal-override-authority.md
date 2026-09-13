# Neural R2.17.1 Temporal Override Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Bind Central override receipts to the exact block frontier that existed when they were issued so later same-artifact blocks make old receipts stale.

**Architecture:** Add an immutable ordered `block_frontier_ids` witness to `OverrideReceipt`. `central_override()` captures the current artifact block IDs; restore verifies the witness against canonical historical block lineage; `can_write()` requires exact equality with the current frontier. Keep the authority top-level state keys unchanged.

**Tech Stack:** Python 3.11/3.13, dataclasses, pytest, GitHub Actions, canonical component-version framework.

**Spec:** `docs/superpowers/specs/2026-09-13-neural-r2171-temporal-override-authority-design.md`

## Global Constraints

- Base: `main@2799fdc4d873eff0a644560e4c58a93f747ebd23`.
- Do not modify historical R2.18 cross-domain-transfer assets.
- No wall-clock expiry, mutable revocation list, or new authority grant.
- Keep top-level authority state keys unchanged.
- Public authority version target: `0.0.2`.
- Implementation revision target: `3` (`0.0.3`).
- Capture hosted RED before production behavior changes.
- Merge only after exact-head matrix and predecessor-baseline comparison.

---

### Task 1: Temporal authority RED

**Files:** Create `tests/test_refoundation_temporal_override_authority.py`.

- [ ] Add live tests proving an override is valid at issuance, becomes stale after a new block on the same artifact, a fresh override restores Central authority, and an unrelated artifact block does not stale it.
- [ ] Add state tests requiring the receipt and serialized override row to expose the exact ordered frontier and preserve it on round-trip.
- [ ] Add restore mutations for missing witness, unknown block ID, wrong-artifact block ID, duplicate ID, and reordered/non-prefix frontier.
- [ ] Add a stale-history round-trip test: restore preserves the old receipt as history but authorization rejects it after a later block.
- [ ] Commit tests only and capture exact hosted RED on Python 3.11 and 3.13.

### Task 2: Minimal authority implementation

**Files:** Modify `nolane/organization/authority.py`.

- [ ] Add `block_frontier_ids: tuple[str, ...]` to `OverrideReceipt` and serialize it as an ordered list.
- [ ] Capture the current artifact block IDs in `central_override()`.
- [ ] Require receipt frontier == current artifact frontier in `can_write()`.
- [ ] Require `block_frontier_ids` during restore; validate canonical IDs, existence, same artifact, uniqueness, and canonical historical order.
- [ ] Permit a valid historical prefix shorter than the current ledger so stale receipts remain auditable; runtime authorization must still reject them.
- [ ] Run the new temporal tests plus R2.17 restore-integrity tests to GREEN on both Python versions.
- [ ] Commit the minimal production change.

### Task 3: Version boundary

**Files:** Modify `nolane/metadata/component_versions.py`, `tests/test_refoundation_component_versions.py`, and temporal tests as needed.

- [ ] Add tests requiring public authority version `0.0.2`, implementation revision `0.0.3`, and next revision `0.0.4`.
- [ ] Observe version RED before changing production versions.
- [ ] Set `nolane.organization.authority.COMPONENT_VERSION = "0.0.2"` and `organization.authority` revision to `3`.
- [ ] Run the canonical runtime fingerprint contract. Because first-generation authority state contains no override rows, the expected outcome is no fingerprint change; if it changes, inspect the actual serialized delta before touching any frozen digest.
- [ ] Run component-version, External Core version-discipline, projection, coherence, and A10 gates to GREEN.

### Task 4: Exact-head acceptance

- [ ] Run final hosted gates: Refoundation Epoch 0, External Core, Memory Learning Substrate, E Acting Transactional Runtime, R1.9, R2.0i, surfaced R2.63/R2.64/R2.64.1 gates, and R2.67.1 Replacement Evidence.
- [ ] Compare any red workflows to predecessor baseline. The four known frozen reds may remain only if unchanged: R2.62 Complementary Causal Program, R2.65 Full Repository Release Bundle, R2.66 Full Repository Release Bundle, R2.67.1 Full Repository Release Bundle.
- [ ] Review final changed-file set and PR threads/comments.
- [ ] Verify base/head/synthetic merge have not drifted, then merge with expected head SHA.
- [ ] Verify `main`, versions, and push-triggered post-merge checks on the returned merge commit.
