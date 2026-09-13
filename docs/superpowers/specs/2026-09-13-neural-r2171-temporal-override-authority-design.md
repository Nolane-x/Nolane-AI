# Neural R2.17.1 — Temporal Override Authority Design

## Context

Neural R2.17 hardened `AuthorityGraph.from_state()` against restore laundering, coercion, identity rebinding, forged override rows, and counter rollback. One temporal authority gap remained: a Central override issued against one block frontier stayed usable after a later independent block was appended for the same artifact because authorization did not bind the receipt to the authority frontier it had actually overridden.

R2.17.1 closes that ABA-style temporal gap without changing ownership semantics or granting new authority.

## Goal

Bind every canonical `OverrideReceipt` to the exact ordered block frontier that existed for its artifact when the override was issued, and preserve enough reciprocal canonical ordering information to prove that restored block/override history is reachable through the live append-only APIs.

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

`AuthorityBlock` gains the reciprocal immutable witness:

```python
override_counter_at_record: int
```

`block_counter_at_issue` records the global block count immediately before an override is appended. `override_counter_at_record` records the global override count immediately before a block is appended. `block_frontier_ids` records the ordered block IDs for the override's target artifact at issuance. These witnesses are serialized inside their existing row ledgers; the top-level authority state shape remains unchanged.

`central_override()` captures the current global block counter and target-artifact frontier. `record_block()` captures the current global override counter.

No third temporal epoch is introduced: R2.17.1 uses the two append-only sequence counters already maintained by `AuthorityGraph` as reciprocal causal witnesses.

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

Restore requires exact canonical block and override rows containing the temporal witnesses.

For each restored override:

- `block_counter_at_issue` is an exact non-negative integer and cannot exceed the restored global block counter;
- every frontier entry is an exact canonical `block-########` string;
- duplicate frontier IDs are rejected;
- the exact historical same-artifact frontier is reconstructed from canonical blocks whose global block sequence number is `<= block_counter_at_issue`;
- stored `block_frontier_ids` must equal that reconstructed frontier exactly and in order;
- `overrode_block` must equal `bool(block_frontier_ids)`.

For each restored block:

- `override_counter_at_record` is an exact non-negative integer and cannot exceed the restored global override counter.

After row-local validation, restore validates the two append-only histories reciprocally. Let `B_i.o` be block `i`'s `override_counter_at_record`, and `O_j.b` be override `j`'s `block_counter_at_issue`. Both sequences must be nondecreasing. For every block and override, the recorded cross-counter must equal the number of opposite-kind events that the reciprocal sequence proves occurred earlier. Equivalently, the two ledgers must encode one common reachable interleaving of block and override append operations.

This reciprocal check matters. A one-sided issuance counter rejects simple frontier rewriting but still permits coordinated forward binding by changing both an override's frontier and its `block_counter_at_issue`. In a true history `B1 -> O1 -> B2`, `B2.override_counter_at_record == 1` witnesses that `O1` already existed before `B2`; therefore rewriting `O1.block_counter_at_issue` from `1` to `2` makes the two ledgers causally inconsistent and restore rejects it.

A historically valid stale receipt may still be restored as audit history. Authorization remains fail-closed because its stored frontier no longer equals the current full same-artifact frontier.

Legacy compatibility is intentionally fail-closed:

- snapshots with no block or override rows remain accepted with the unchanged top-level shape;
- override-bearing snapshots missing their temporal witnesses are rejected rather than guessed or implicitly migrated;
- block-bearing snapshots for this release must carry the reciprocal block witness.

## Security boundary

The guarantee is structural reachability, not cryptographic authenticity. R2.17.1 rejects malformed, one-sided, and reciprocally inconsistent temporal histories, including stale-receipt resurrection through coordinated override-only rewriting.

It cannot distinguish an honest reachable history from a completely rewritten alternative history if an attacker can consistently alter every mutually constraining row. That stronger origin-authenticity property requires an external trusted signature, MAC, append-only ledger, or equivalent provenance anchor and is outside this milestone.

## Public and implementation versions

This changes the public immutable authority row shapes and serialized temporal semantics.

- `nolane.organization.authority.COMPONENT_VERSION`: `0.0.1 -> 0.0.2`.
- canonical implementation revision for `organization.authority`: `2 -> 3` (`0.0.3`).

The reciprocal causal-witness hardening is part of the same unmerged R2.17.1 semantic boundary and does not consume another revision.

The top-level authority state keys remain unchanged. First-generation runtime state contains no block or override rows, so the accepted first-generation runtime fingerprint remains `90fbbb26ca1519d957c4507291bd503f7d0b1fbf8d1929924e83d9f3c6050ed3`; acceptance verifies it through the Refoundation fingerprint contract.

## TDD evidence model

R2.17.1 uses layered RED evidence:

1. temporal-authority RED for stale/fresh same-artifact authorization, unrelated-artifact independence, serialization/round-trip, malformed restore rows, and declared version boundaries;
2. simple forward-binding RED proving `block_frontier_ids` alone could be moved to the current frontier;
3. coordinated forward-binding RED proving `block_counter_at_issue` plus the frontier was still one-sided and could be jointly forged.

The third RED is the decisive causal-order contract: honest stale state must remain restorable and unauthorized, while jointly advancing both override witnesses without reciprocal block history must be rejected.

## Acceptance boundary

Acceptance requires hosted GREEN on Python 3.11 and 3.13 for the temporal-authority contracts plus Refoundation Epoch 0, External Core/version discipline, Memory Learning Substrate, E Acting transactional runtime, R1.9, R2.0i, and the surfaced protected lineage gates. Historical frozen workflow failures are compared against the accepted predecessor and are not relabeled as regressions.
