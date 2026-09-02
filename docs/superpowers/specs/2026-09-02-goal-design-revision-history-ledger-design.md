# Goal/Design Revision History Ledger Design

## Status

Implementation authority for the next D. Goal / Design hardening wave. This design projects the already-accepted Goal Integrity contract/evolution authority into a deterministic, typed, provider-neutral revision-history ledger. It does not create a second goal authority, does not infer missing provenance, and does not rewrite historical contract or evolution-receipt identities.

## Problem

Goal/Design already has strong mutation authority:

- immutable Goal Integrity Contracts;
- exact predecessor chains;
- explicit evolution receipts;
- verifier-backed transition authorization;
- restart validation and anti-rollback checks;
- truthful legacy trust classes.

What is still missing is a first-class public history artifact. A consumer currently has to know private runtime maps and several generations of compatibility state to answer basic questions such as: what was the root contract, which revision superseded it, what exact delta was authorized, what evidence/freshness/confidence accompanied the transition, what trust class does each historical edge have, and can the same history be reproduced after restart?

The locked NC02 Goal, Intent & Constraint Core requirements make this a P0 gap. Goal revision history requires a versioned typed contract, canonical serialization, deterministic public records, explicit trust labels, bounded fields, source lineage, freshness, transformation history, calibrated confidence/uncertainty, and tamper-evident restart verification.

## Architectural boundary

Add `nolane/external_core/goal_design_revision_history.py` as a read-only projection layer over accepted Goal/Design authority.

The ledger is not a mutation path:

- contracts remain authoritative in `GoalIntegrityRuntime`;
- predecessor topology remains authoritative in the existing runtime archive;
- structural deltas remain authoritative in `assess_goal_integrity_evolution(...)`;
- evolution receipts remain authoritative for source/evidence/freshness/confidence;
- `evolution_trust_label(...)` remains authoritative for historical trust class;
- verifier state remains the authority for capability authenticity;
- the ledger may expose these facts but cannot mint, revise, revoke, reactivate, or promote any of them.

No provider, model, tool, browser, repository content, or free-text inference participates in ledger construction. The local projection is deterministic and bounded by already-resident contract history.

## Protocol contract

### Schema

`GOAL_REVISION_HISTORY_SCHEMA_VERSION = 1`.

The public module exposes one capability descriptor:

`GoalRevisionHistoryProtocol`

Fields:

- `schema_version`
- `protocol_name = "nolane.goal_design.revision_history"`
- canonical `capabilities`
- canonical `compatible_schema_versions`
- derived `digest`

Initial capabilities:

- `canonical_history`
- `explicit_trust`
- `source_lineage`
- `freshness_state`
- `transformation_history`
- `bounded_uncertainty`
- `tamper_evident_identity`
- `restart_replay`

Only schema v1 is accepted in this wave. Unknown requested versions fail closed rather than silently downgrading.

### Trust and evidence completeness

The ledger must never promote legacy state merely because it can be serialized.

`GoalRevisionEvidenceStatus`:

- `VERIFIED` — an explicit receipted transition with verified capability authority;
- `LEGACY_UNVERIFIED` — an explicit historical receipt whose authority authenticity predates verifier enforcement;
- `LEGACY_UNATTESTED` — historical revision with no explicit evolution receipt;
- `ROOT_UNATTESTED` — root contract has no evolution edge/receipt.

These evidence statuses are projection labels. For non-root revisions, the authoritative trust string is still obtained from `GoalIntegrityRuntime.evolution_trust_label(...)` and embedded unchanged.

### Freshness

`GoalRevisionFreshnessStatus`:

- `ATTESTED` — the evolution receipt carries its exact non-empty `freshness_ref`;
- `UNATTESTED` — no truthful freshness reference exists.

The ledger never manufactures timestamps or claims that an opaque freshness reference is currently fresh. It records what was attested at authorization time.

### Confidence and uncertainty

Every entry carries bounded uncertainty semantics without fabricating confidence:

- if an explicit evolution receipt exists, `confidence_milli` is copied exactly from the receipt and `uncertainty_milli = 1000 - confidence_milli`;
- root or legacy-unattested entries use `confidence_milli = None` and `uncertainty_milli = 1000`.

This is a conservative absence-of-evidence representation, not a claim that uncertainty has been statistically calibrated by a model.

## `GoalRevisionHistoryEntry`

Immutable, content-addressed fields:

- `sequence`
- `goal_id`
- `contract_digest`
- `predecessor_digest | None`
- `successor_is_current`
- `contract_clause_ids`
- `metric_ids`
- `delta_digest | None`
- added/removed/changed clause IDs
- added/removed/changed metric IDs
- `evolution_receipt_id | None`
- `authority_ref | None`
- `trust_label`
- `evidence_status`
- canonical `source_refs`
- canonical `evidence_refs`
- `freshness_status`
- `freshness_ref | None`
- `confidence_milli | None`
- `uncertainty_milli`
- canonical `transformation_refs`
- derived `entry_id`

For a receipted revision, `transformation_refs` includes predecessor digest, delta digest, successor digest, and receipt ID. For an unattested historical edge it includes only topology and a freshly re-derived structural delta; the absence of receipt authority remains visible.

For the root entry, source lineage is limited to provenance references already present in its integrity clauses. It has no predecessor, delta, receipt, authority reference, or attested freshness/confidence.

All strings and reference collections are bounded using limits equivalent to the accepted evolution-receipt protocol. An entry cannot smuggle unbounded provider output into the public record.

## `GoalRevisionHistoryLedger`

Immutable, content-addressed fields:

- `schema_version`
- `protocol_digest`
- `goal_id`
- `current_contract_digest`
- canonical ordered `entries`
- aggregate `source_refs`
- aggregate `evidence_refs`
- `history_digest`

The ordered entries are the unique root-to-head chain, not sorting by arbitrary contract digest. Sequence zero is the root and the final entry must be the runtime's exact current contract.

`history_digest` binds protocol version, goal, current head, every entry ID, and aggregate evidence/source refs. Identical sealed runtime authority produces identical history identity.

## Projector

`GoalRevisionHistoryProjector.project(...)` consumes only explicit, validated authority inputs:

```python
def project(
    self,
    *,
    goal_id: str,
    contracts: Mapping[str, GoalIntegrityContract],
    current_digest: str,
    predecessors: Mapping[str, str | None],
    evolution_receipts: Mapping[str, GoalIntegrityEvolutionReceipt],
    trust_labels: Mapping[str, str],
) -> GoalRevisionHistoryLedger:
    ...
```

Before emitting output it must prove:

1. every referenced contract exists and belongs to the requested goal;
2. the requested current digest exists and belongs to that goal;
3. one and only one root reaches the current digest;
4. no self-edge, cross-goal edge, unknown predecessor, branch, cycle, or disconnected contract for that goal exists;
5. every explicit receipt re-verifies against its exact predecessor/successor and re-derived delta;
6. every non-root revision has exactly one truthful trust class;
7. a verified/legacy-unverified trust class requires an explicit receipt;
8. legacy-unattested may not carry a fabricated receipt;
9. root cannot carry evolution authority;
10. canonical bounds are respected before digest construction.

The projector treats inputs as untrusted serialized/runtime material even though the strongest public caller will provide already-validated state. This defense-in-depth makes the artifact independently testable and keeps malformed input fail closed.

## Runtime seam

The strongest public API is:

```python
GoalIntegrityRuntime.goal_revision_history(
    goal_id: str,
    *,
    schema_version: int = GOAL_REVISION_HISTORY_SCHEMA_VERSION,
) -> GoalRevisionHistoryLedger
```

Runtime behavior:

- ensure integrity/evolution/authenticity state exists;
- require the goal to have a current contract;
- negotiate exact supported schema version;
- select only contracts belonging to that goal;
- derive trust labels through existing runtime authority;
- delegate to one local deterministic projector;
- perform no state mutation.

A caller cannot supply contracts, receipts, trust labels, freshness, confidence, or arbitrary history entries through this seam.

## Restart verification

No separate mutable history database is introduced. Persistence already belongs to `GoalIntegrityRuntime.integrity_state()`.

The restart invariant is stronger and simpler:

1. runtime A produces `ledger_a`;
2. runtime A serializes its existing authenticated integrity state;
3. runtime B restores that state through existing atomic validation;
4. runtime B re-projects `ledger_b`;
5. `ledger_b.history_digest == ledger_a.history_digest` and entry IDs are byte-for-byte deterministic.

Tampered nested receipts, topology, current-head rewinds, trust-class laundering, or malformed authority state must be rejected by restore/projector before a new ledger can be emitted.

## Failure semantics

This wave does not add a generic recovery executor. It exposes bounded fail-closed behavior consistent with the existing runtime:

- unknown goal: `KeyError` / `CoherenceError` at runtime boundary;
- unsupported schema: `ValueError` / `CoherenceError`;
- malformed topology: reject projection;
- tampered receipt: reject projection;
- mismatched trust provenance: reject projection;
- failed restore: existing populated verified runtime remains unchanged because restore validates into temporary state before assignment;
- no partial history is returned after any validation failure.

A later failure-recovery wave may add explicit recovery-action records, but it must not weaken these atomic semantics.

## Security boundary

The ledger is deliberately local and deterministic:

- no provider/model calls;
- no command execution;
- no path access;
- no browser access;
- no repository fetches;
- no secret input fields;
- no caller-supplied trust promotion;
- no free-text interpretation;
- no authority keys serialized or exposed.

Opaque source/evidence/freshness references are data labels only. They are never dereferenced by the projector.

## Local-first profile

Projection is O(number of contracts/revisions for one goal) with bounded per-entry reference collections. It requires no cloud service, GPU, local model, vector index, or background worker. The same semantic output is produced on Python 3.11 and 3.12 for identical sealed inputs.

## Compatibility

- Existing GoalIntegrityContract identities remain unchanged.
- Existing v1 evolution receipt identities remain unchanged.
- Existing v1/v2/v3 integrity runtime state remains unchanged in this wave.
- Historical `legacy_unattested` and `legacy_unverified_authority` records remain truthful and visible.
- Ledger schema v1 is additive and provider-neutral.
- Unsupported future ledger versions fail closed until explicitly implemented.

## Adversarial verification

TDD and final tests must cover:

- public runtime seam absent before implementation (behavioral RED, not import failure);
- root-only history;
- verified multi-revision chain;
- deterministic identity under mapping insertion-order changes;
- exact source/evidence/freshness/confidence projection;
- root maximum-uncertainty semantics without fabricated confidence;
- legacy-unverified and legacy-unattested labels remain distinct;
- unknown goal and unsupported schema fail closed;
- wrong current head, unknown predecessor, branch, cycle, disconnected revision, cross-goal contract reject;
- explicit receipt with wrong successor/predecessor/delta rejects;
- trust/receipt mismatch rejects;
- canonical bounds reject oversized injected refs;
- restart re-projection returns identical history digest;
- tampered persisted runtime state cannot yield a ledger;
- history compilation has no mutation side effects.

Final acceptance requires all `tests/test_goal_design*.py` on Python 3.11/3.12, Refoundation Epoch 0 on Python 3.11/3.13, R1.9, R2.0i, latest-main race guard, exact-union rebuild on concurrent drift, expected-head protected merge, and post-merge actual-main verification.