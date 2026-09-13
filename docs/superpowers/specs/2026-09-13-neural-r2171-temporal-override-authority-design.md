# Neural R2.17.1 — Temporal Override Authority Design

## Context

Neural R2.17 hardened `AuthorityGraph.from_state()` against restore laundering, coercion, identity rebinding, forged override rows, and counter rollback. One temporal authority gap remains: a Central override issued against one block frontier stays usable after a later independent block is appended for the same artifact because `can_write()` currently checks only actor identity and artifact identity.

This milestone closes that ABA-style temporal gap without changing ownership semantics or granting new authority.

## Goal

Bind every canonical `OverrideReceipt` to the exact ordered block frontier that existed for its artifact when the override was issued. An override is valid only while the artifact's current canonical block frontier exactly matches the receipt's captured frontier.

## Non-goals

- Do not add override expiration by wall-clock time.
- Do not add mutable revocation lists.
- Do not change owner claim semantics.
- Do not weaken independent blocks.
- Do not change the top-level `AuthorityGraph.to_state()` keys.
- Do not modify historical R2.18 cross-domain-transfer research or its branches/workflows.

## Canonical data model

`OverrideReceipt` gains one public immutable field:

```python
block_frontier_ids: tuple[str, ...]
```

The field is serialized as an ordered JSON list named `block_frontier_ids` inside each override row. The order is the append order returned by `blocks_for(artifact_id)`.

`central_override()` captures:

```python
block_frontier_ids = tuple(
    block.block_id for block in self._blocks.get(str(artifact_id), ())
)
```

This witness is content-addressed by the existing canonical state rather than by time. No new global epoch counter is introduced.

## Authority invariant

For `can_write(actor, artifact, override_id=...)` to return true, all existing conditions must remain true and additionally:

```python
receipt.block_frontier_ids == tuple(
    block.block_id for block in self._blocks.get(artifact, ())
)
```

Consequences:

1. An override created after blocks `B1..Bn` is valid against exactly `B1..Bn`.
2. Appending `Bn+1` for the same artifact immediately makes the old override stale.
3. Appending a block for another artifact does not affect the receipt.
4. Central may regain authority only by issuing a new override with new evidence, creating a new receipt bound to the new frontier.
5. An override issued when no blocks exist captures an empty frontier. If a later block appears, that receipt becomes stale.

## Restore invariants

`AuthorityGraph.from_state()` must fail closed unless every override row has an exact canonical `block_frontier_ids` list.

For each frontier entry:

- value is an exact string;
- ID uses canonical `block-########` form;
- ID exists in the restored canonical block ledger;
- the referenced block belongs to the same artifact as the override;
- no duplicate frontier IDs are allowed;
- frontier order exactly matches a prefix equal to the full current block frontier for that artifact at snapshot time.

Because a snapshot contains only the current append-only block ledger, accepted serialized overrides must therefore bind to a canonical historical prefix of that ledger. A receipt may be stale at restore time and still be preserved as history; `can_write()` must reject it unless its stored frontier equals the current full frontier. This distinction is important: restore validates historical authenticity, while authorization validates current temporal freshness.

Legacy compatibility is fail-closed:

- snapshots with no override rows remain accepted with the unchanged top-level state shape;
- snapshots containing override rows without `block_frontier_ids` are rejected rather than guessed or migrated implicitly.

## Public and implementation versions

This changes the public immutable `OverrideReceipt` shape and serialized override-row semantics.

- `nolane.organization.authority.COMPONENT_VERSION`: `0.0.1 -> 0.0.2`.
- canonical implementation revision for `organization.authority`: `2 -> 3` (`0.0.3`).

The top-level authority state keys remain unchanged. First-generation runtime state is expected to keep the same fingerprint because the first-generation authority graph contains no override receipts; this must be verified rather than assumed.

## Error handling

Malformed temporal witnesses raise `ValueError` during restore. Runtime stale overrides are not malformed state, so `can_write()` returns `False` and `require_write()` follows the existing blocked/unauthorized `PermissionError` behavior.

## Test strategy

The test-only RED phase must prove at least these behaviors before production changes:

1. an override is valid against the frontier it captured;
2. adding a new same-artifact block makes that override stale;
3. issuing a fresh override after the new block restores Central write authority;
4. a block on another artifact does not stale the receipt;
5. live receipt and serialized state expose the exact frontier;
6. round-trip preserves the frontier;
7. restore rejects a missing frontier field on an override-bearing snapshot;
8. restore rejects unknown block IDs;
9. restore rejects block IDs from another artifact;
10. restore rejects duplicate frontier IDs;
11. restore rejects reordered/non-prefix frontier witnesses;
12. restore may preserve a historically valid stale receipt, but `can_write()` rejects it after restore;
13. public version and implementation revision advance exactly as declared;
14. existing first-generation runtime fingerprint remains unchanged if its authority state contains no overrides.

## Acceptance boundary

Acceptance requires hosted GREEN on supported Python 3.11 and 3.13 for the focused temporal-authority tests plus the Refoundation Epoch 0, External Core/version discipline, Memory Learning Substrate, E Acting transactional runtime, R1.9, and R2.0i gates. Historical frozen workflow failures must be compared against the accepted predecessor and must not be relabeled as regressions.
