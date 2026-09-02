# Goal/Design Revision History Ledger Design

## Status

Implementation authority for the next D. Goal / Design hardening wave. This design projects the already-authenticated Goal Integrity contract/evolution topology into a first-class public revision-history contract. It does not create a second evolution engine, grant mutation permission, replace Family-A truth authority, or rewrite historical contract/evolution receipt identities.

## Locked requirements

This wave targets NC02 Goal, Intent & Constraint Core / goal revision history P0 requirements:

- versioned, typed, provider-neutral contract with canonical serialization, explicit trust labels, bounded fields, capability negotiation, and forward/backward compatibility;
- deterministic public record for identical sealed state/configuration;
- source lineage, freshness, transformation history, calibrated confidence/uncertainty, and a tamper-evident receipt verifiable after restart;
- fail-closed behavior for malformed/stale/contradictory history state without silently replacing the last verified Goal Integrity state;
- local-first operation with no required cloud/provider/model dependency.

Security is conservative: the ledger projects only already-installed runtime facts. Untrusted external/provider/browser/repository prose is never parsed or promoted by the history compiler.

## Existing authority reused

The ledger consumes, but never duplicates:

1. immutable `GoalIntegrityContract` archive and exact predecessor topology from the integrity runtime;
2. `GoalIntegrityEvolutionReceipt` transition evidence, source refs, freshness ref and confidence;
3. v0.3 runtime trust provenance classes: `verified_capability_authority`, `legacy_unverified_authority`, and `legacy_unattested`;
4. existing restore validation that rejects branch/cycle/current-pointer rewind/missing-receipt/tampered authority state.

The ledger is a read-only projection. A history object has zero mutation authority.

## Protocol

Protocol name: `nolane.goal_revision_history`.

Initial supported version: major `1`, minor `0`.

Major-version mismatch is incompatible and fails closed. A caller may request `protocol_major=1` and a `minimum_minor` not greater than the runtime-supported minor. Minor additions are backward-compatible only when existing field meanings and digest rules remain unchanged. New incompatible digest semantics require a new major.

### `GoalRevisionHistoryCapability`

Immutable fields:

- `protocol_name`
- `major`
- `minor`
- canonical `features`
- derived `digest`

Initial features:

- `canonical_entry_chain`
- `explicit_trust_provenance`
- `restart_verifiable_receipt`
- `truthful_legacy_missingness`
- `local_deterministic_projection`

### `GoalRevisionHistoryEntry`

Immutable, bounded, content-addressed representation of exactly one contract node:

- `goal_id`
- `ordinal` starting at `0` for the root
- `contract_digest`
- `predecessor_digest: str | None`
- `evolution_receipt_id: str | None`
- `delta_digest: str | None`
- `trust_label`
- canonical `source_refs`
- canonical `evidence_refs`
- `freshness_ref: str | None`
- `confidence_milli: int | None`
- canonical `transformation_history`
- `previous_entry_digest: str | None`
- derived `entry_digest`

Root semantics are explicit, not fabricated:

- trust label is `root_integrity_contract`;
- source lineage is derived only from contract clause/metric provenance that actually exists;
- no evolution receipt/delta/freshness/confidence is invented; those fields are `None` when unavailable;
- transformation history records deterministic projection steps, not claims about external evidence.

Revision semantics:

- predecessor/successor/delta are re-verified against the installed immutable contracts and receipt;
- source/evidence/freshness/confidence come exactly from the evolution receipt when one exists;
- legacy revisions without an explicit receipt expose empty evidence/source collections where unavailable and `None` freshness/confidence rather than synthesizing evidence;
- trust label comes from `GoalIntegrityRuntime.evolution_trust_label(...)`, never from caller input.

### `GoalRevisionHistorySnapshot`

Immutable public record:

- capability
- `goal_id`
- `current_contract_digest`
- canonical topology-ordered `entries`
- `history_digest`

`history_digest` binds protocol capability, exact current head and the ordered entry digest chain. Insertion order of internal dictionaries cannot affect it.

### `GoalRevisionHistoryReceipt`

Tamper-evident public receipt:

- protocol major/minor
- `goal_id`
- `history_digest`
- `current_contract_digest`
- `entry_count`
- `receipt_id`

`receipt_id` is a deterministic digest of the receipt payload. Verification recomputes every entry digest, chain link, history digest, current head binding and receipt identity. The receipt is evidence of a deterministic projection, not permission to revise a goal.

### `GoalRevisionHistoryExport`

A simple immutable pair:

- `snapshot`
- `receipt`

## Compiler

`GoalRevisionHistoryCompiler.compile(...)` accepts only runtime-owned immutable facts:

- goal ID;
- current contract digest;
- contract mapping;
- predecessor mapping;
- evolution receipt mapping;
- trust-label resolver;
- requested protocol major/minimum minor.

It must:

1. negotiate protocol before projection;
2. derive the unique root -> current chain by predecessor topology, never dict insertion order;
3. require every chain node to belong to the requested goal;
4. require the current pointer to equal the unique chain head;
5. re-verify each explicit evolution receipt against exact predecessor/successor contracts;
6. require every non-root node to have exactly one truthful trust provenance class from the runtime;
7. build canonical bounded entries and their previous-entry digest chain;
8. mint the snapshot and deterministic receipt;
9. verify the produced export before returning it.

Any impossible topology, missing contract, cross-goal edge, invalid receipt, unsupported capability, or trust-resolution failure raises `ValueError` before any public output is returned.

## Runtime seam

Add:

```python
GoalIntegrityRuntime.goal_revision_history(
    goal_id: str,
    *,
    protocol_major: int = 1,
    minimum_minor: int = 0,
) -> GoalRevisionHistoryExport
```

The runtime:

- calls `_ensure_authority_authenticity_state()` first;
- requires the goal to have a current installed contract;
- passes read-only snapshots/copies of its contract/predecessor/evolution mappings into one `GoalRevisionHistoryCompiler` instance;
- resolves trust through its existing `evolution_trust_label` method;
- converts compiler validation failures to `CoherenceError` at the public control-plane boundary;
- performs no mutation and does not serialize the compiler itself into historical integrity-state schemas.

## Restart verification

A successful `integrity_state()` -> fresh runtime `restore_integrity_state(...)` round trip must produce byte-equivalent history semantics: identical ordered entry digests, history digest and receipt ID for the same goal and protocol.

The ledger does not persist a second copy of history. Existing integrity-state restore remains the single source of truth and already validates topology/receipt/authenticity. This avoids partial-write divergence between two stores.

## Failure and recovery boundary

The safest bounded recovery for this wave is **re-project from the last successfully restored Goal Integrity state**. There is no history-side repair mutation API. If persisted integrity state is malformed, stale, contradictory or partial, existing atomic/fail-closed restore rejects it; the ledger cannot launder that state into a public history. If a live in-memory topology is corrupted, history export fails closed and does not mutate or replace the installed contracts.

Provider timeout/malformed model output is outside this projection layer because it makes zero provider/model calls. Any future provider-backed goal-revision proposal system must remain upstream and may only enter history after normal authenticated evolution acceptance.

## Security and local-first invariants

- no network, provider, browser, repository or model call;
- no free-text interpretation or prompt execution;
- no secrets/authority keys in history output;
- verifier authentication keys remain outside serialized runtime/history state;
- caller cannot supply trust labels, receipt fields, topology or provenance to the runtime seam;
- bounded text/reference/count fields prevent unbounded public history metadata;
- history projection complexity is linear in the goal's revision count and suitable for an 8 GB local profile.

## Compatibility

- historical Goal Integrity v1/v2/v3 state remains readable by the existing runtime migration logic;
- root-only histories work without an evolution receipt;
- v1 migrated revisions expose `legacy_unattested` and truthful missing evidence fields;
- v2 migrated receipted revisions expose `legacy_unverified_authority` plus the exact historical receipt metadata;
- v3 verified revisions expose `verified_capability_authority` plus the exact receipt metadata;
- no existing `GoalIntegrityContract`, `GoalIntegrityEvolutionReceipt`, `DecisionReceipt`, or integrity-state digest identity changes.

## Verification strategy

Hosted TDD RED must be behavioral: construct a current runtime with a root and one verifier-authorized revision, then call `runtime.goal_revision_history(...)`. Current production must fail because that public seam does not exist. A missing-module collection failure does not count.

GREEN/adversarial coverage must prove:

- root-only typed deterministic export;
- verified root -> revision export carries exact receipt lineage/freshness/confidence/trust;
- repeated export and internal mapping reorder produce identical history/receipt IDs;
- multiple revisions are topology ordered and hash chained;
- wrong major / too-new minor fail closed;
- foreign-goal/cross-goal/missing predecessor/current-head rewind cannot be exported;
- explicit receipt tamper or wrong transition cannot be exported;
- legacy trust classes remain truthful and missing metadata is never fabricated;
- caller cannot inject trust/provenance;
- restart round trip yields identical history receipt;
- export has no side effects on contracts, decisions, integrity authority or verifier state;
- no provider/cloud dependency exists.

Final acceptance repeats the D discipline: Goal Design Python 3.11/3.12, Refoundation Python 3.11/3.13, R1.9, R2.0i, latest-main race guard, expected-head protected merge, then actual-main Goal Design + R1.9 + R2.0i verification.