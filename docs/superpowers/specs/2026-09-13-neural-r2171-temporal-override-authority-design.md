# Neural R2.17.1 — Temporal Override Authority Design

## Context

Neural R2.17 hardened `AuthorityGraph.from_state()` against restore laundering, coercion, identity rebinding, forged override rows, and counter rollback. One temporal authority gap remained: a Central override issued against one block frontier stayed usable after a later independent block was appended for the same artifact because authorization did not bind the receipt to the authority frontier it had actually overridden.

R2.17.1 closes that ABA-style temporal gap without changing ownership semantics or granting new authority.

## Goal

Bind every canonical `OverrideReceipt` to the exact ordered block frontier that existed for its artifact when the override was issued, and preserve enough canonical issuance-order information to reconstruct that historical frontier during restore.

An override is valid only while the artifact's current canonical block frontier exactly matches the receipt's captured frontier.

## Non-goals

- No wall-clock expiration.
- No mutable revocation list.
- No new authority grant.
- No owner-claim semantic change.
- No new top-level `AuthorityGraph.to_state()` key.
- No modification of historical R2.18 cross-domain-transfer research.
- No claim of cryptographic authenticity. This milestone enforces canonical structural temporal consistency; it does not protect against an attacker able to rewrite all mutually consistent canonical state without an external trusted anchor.

## Canonical data model

`OverrideReceipt` gains two public immutable temporal witness fields:

```python
block_counter_at_issue: int
block_frontier_ids: tuple[str, ...]
```

`block_counter_at_issue` records the existing global append-only block counter at issuance. `block_frontier_ids` records the ordered block IDs for the target artifact at that same point. Both are serialized inside each override row; the top-level authority state shape remains unchanged.

`central_override()` captures the current global block counter and the target artifact's current block IDs before creating the receipt.

No independent temporal epoch counter is introduced: R2.17.1 reuses the canonical global block sequence already maintained by `AuthorityGraph`.

## Authority invariant

For `can_write(actor, artifact, override_id=...)` to return true, all existing identity/artifact conditions remain required and additionally:

```python
receipt.block_frontier_ids == tuple(
    block.block_id for block in self._blocks.get(artifact, ())
)
```

Consequences:

1. An override issued against `B1..Bn` authorizes exactly that same-artifact frontier.
2. Appending `Bn+1` for that artifact immediately makes the old override stale.
3. Appending a block for another artifact does not stale the receipt.
4. Central may regain authority only by issuing a new evidence-backed override bound to the new frontier.
5. An override issued when no blocks exist captures an empty frontier; a later block makes it stale.

## Restore invariants

Restore must require exact canonical override rows containing both temporal fields.

For every restored override:

- `block_counter_at_issue` is an exact non-negative integer and cannot exceed the restored global block counter;
- every frontier entry is an exact canonical `block-########` string;
- duplicate frontier IDs are rejected;
- the exact historical same-artifact frontier is reconstructed from canonical blocks whose global block sequence number is `<= block_counter_at_issue`;
- stored `block_frontier_ids` must equal that reconstructed frontier exactly and in order;
- `overrode_block` must equal `bool(block_frontier_ids)`.

This exact reconstruction matters. A weaker "any historical prefix" rule is insufficient: an attacker could otherwise forward-bind a stale override to a later frontier in serialized state and revive it after restore.

A historically valid stale receipt may still be restored as audit history. Authorization remains fail-closed because its stored frontier no longer equals the current full same-artifact frontier.

Legacy compatibility is intentionally fail-closed:

- snapshots with no override rows remain accepted with the unchanged top-level shape;
- override-bearing snapshots missing either temporal witness field are rejected rather than guessed or implicitly migrated.

## Security boundary

The guarantee is structural, not cryptographic. Given canonical block history, R2.17.1 prevents omission, prefix substitution, cross-artifact substitution, duplicate/reordered frontier rows, counter rollback/forward binding, and stale-receipt resurrection that violate reachable `AuthorityGraph` history.

It does not prove origin authenticity against a party that can rewrite the complete snapshot into another mutually consistent reachable history. That stronger property would require a trusted external signature, digest anchor, or equivalent provenance mechanism and is outside this milestone.

## Public and implementation versions

This changes the public immutable `OverrideReceipt` shape and serialized override-row semantics.

- `nolane.organization.authority.COMPONENT_VERSION`: `0.0.1 -> 0.0.2`.
- canonical implementation revision for `organization.authority`: `2 -> 3` (`0.0.3`).

The audit hardening that added `block_counter_at_issue` is part of the same R2.17.1 semantic boundary and does not consume another revision.

The top-level authority state keys remain unchanged. First-generation runtime state has no override receipts, so no runtime-fingerprint cutover is expected; acceptance must verify this rather than assume it.

## TDD evidence model

R2.17.1 has two RED layers:

1. the original temporal-authority RED proving same-artifact staleness, fresh reauthorization, unrelated-artifact independence, serialization/round-trip, malformed frontier rejection, and the declared version boundary;
2. an adversarial review RED proving that `block_frontier_ids` alone was insufficient because a stale receipt could be forward-bound to the current frontier during restore.

The second RED adds direct contracts for `block_counter_at_issue`, missing issuance witness rejection, and forward-bound stale-override rejection before the production repair.

## Acceptance boundary

Acceptance requires hosted GREEN on Python 3.11 and 3.13 for the temporal-authority contracts plus Refoundation Epoch 0, External Core/version discipline, Memory Learning Substrate, E Acting transactional runtime, R1.9, R2.0i, and the surfaced protected lineage gates. Historical frozen workflow failures are compared against the accepted predecessor and are not relabeled as regressions.
