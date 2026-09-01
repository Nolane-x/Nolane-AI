# Goal/Design Revision History Ledger Design

## Status

Implementation authority for the next D. Goal / Design hardening wave. This design adds a typed, deterministic, read-only goal revision history ledger over the already accepted Goal Integrity contract/evolution runtime. It does not create a second evolution authority, does not mutate historical receipts, and does not promote legacy evidence.

## Problem

Goal Integrity already has immutable contracts, exact predecessor chains, deterministic structural deltas, evolution receipts, verifier-backed capability authority, trust classes, tamper-evident runtime state, and fail-closed restore. What is missing is a public revision-history contract that exposes that authority as one canonical, restart-verifiable history artifact.

Without such a ledger, downstream consumers must inspect private runtime dictionaries and combine contracts, predecessor links, receipts, and trust labels themselves. That creates inconsistent serialization, evidence omission, silent trust inflation, and accidental reliance on internal state layout.

The locked NC02 requirements require goal revision history to provide a versioned typed provider-neutral contract, deterministic public record, source lineage, freshness, transformation history, calibrated uncertainty/confidence, tamper-evident restart verification, fail-closed recovery semantics, security boundaries, and a complete local-first profile.

## Architectural boundary

The ledger is a pure projection of already-authorized D state:

`GoalIntegrityRuntime state -> GoalRevisionHistoryProjector -> GoalRevisionHistoryLedger`

It is not mutation authority. It never installs contracts, issues grants, authorizes revisions, revalidates truth, performs provider calls, or reads repository/browser/user content.

A verified evolution receipt remains the authority for a transition. The ledger only packages exact existing authority into a stable public history contract.

## Public components

### `GoalRevisionTrust`

Typed public trust labels:

- `ROOT_CONTRACT` — original root contract; no predecessor/evolution receipt exists.
- `VERIFIED_CAPABILITY_AUTHORITY` — revision whose transition is backed by verifier-authenticated capability authority.
- `LEGACY_UNVERIFIED_AUTHORITY` — historical explicit receipt exists but its authority authenticity was not verifier-backed at acceptance time.
- `LEGACY_UNATTESTED` — historical revision has no explicit evolution receipt.

Legacy values are intentionally weaker and cannot be promoted by projection.

### `GoalRevisionRecord`

Immutable, content-addressed record for exactly one contract revision:

- `schema_version`
- `goal_id`
- `ordinal`
- `contract_digest`
- optional `predecessor_digest`
- `trust`
- optional `evolution_receipt_id`
- optional `delta_digest`
- canonical `source_refs`
- canonical `evidence_refs`
- optional `freshness_ref`
- optional `confidence_milli`
- canonical `transformation_refs`
- `is_current`
- derived `record_id`

Root and legacy-unattested entries must expose unavailable provenance as empty/`None`; they must never fabricate evidence, freshness, confidence, or receipt identity.

For explicit revisions, `transformation_refs` contains the exact delta digest and evolution receipt identity. For root entries it is empty.

### `GoalRevisionHistoryLedger`

Immutable, content-addressed public ledger:

- `schema_version`
- `goal_id`
- `current_contract_digest`
- ordered tuple of `GoalRevisionRecord`
- `runtime_state_digest`
- `ledger_id`

Records are ordered by exact predecessor topology from root to current head, never by insertion order or dictionary order.

`ledger_id` binds the schema version, goal, current head, ordered record IDs, and the exact runtime-state digest used to project the ledger.

### `GoalRevisionHistoryProjector`

Pure deterministic projector. Given one `GoalIntegrityRuntime` and `goal_id`, it:

1. obtains canonical `integrity_state()` and verifies the public state digest already produced by the runtime;
2. resolves the exact root->head predecessor chain for the requested goal;
3. rejects missing roots, branches, cycles, disconnected nodes, foreign-goal contracts, or a current pointer that is not the unique head;
4. for each explicit revision, re-verifies `GoalIntegrityEvolutionReceipt` against exact predecessor/successor contracts and re-derives its structural delta;
5. maps runtime trust provenance to the typed public trust enum without strengthening it;
6. emits one deterministic record per contract and one deterministic ledger.

The projector performs no I/O and no nondeterministic selection.

## Runtime seam

`GoalIntegrityRuntime.goal_revision_history(goal_id: str) -> GoalRevisionHistoryLedger`

This is the strongest public seam because the runtime owns contract topology, receipt archive, trust classification, and current-head state.

The method delegates to one pure projector and must not expose private dictionaries directly.

## Determinism

Identical sealed runtime state and `goal_id` must produce byte-equivalent semantic data and the same record/ledger identities regardless of insertion order.

No model call, clock read, random value, process-local identity, or provider output participates in projection.

## Evidence and freshness semantics

Explicit evolution receipts already bind `source_refs`, `evidence_refs`, `freshness_ref`, `confidence_milli`, reason, authority reference, predecessor/successor, and delta digest. The ledger carries those fields exactly.

Root contracts and legacy-unattested revisions have no such evidence contract. The ledger truthfully exposes that absence. A consumer can therefore distinguish "verified evidence exists" from "history exists but provenance is weaker".

## Restart verification

The public ledger is verifiable after restart by restoring the runtime through the existing fail-closed restore path and re-projecting the ledger. Identical accepted state must reproduce the same `ledger_id`.

A ledger does not become an independent source of restoration authority. Restoring from a ledger alone is explicitly unsupported; the canonical runtime state remains the restart authority.

## Failure and recovery boundary

The projector is failure-atomic because it is read-only. Any malformed topology, stale current pointer, receipt mismatch, trust-class mismatch, or state-digest mismatch raises before returning a ledger. The last verified runtime state remains unchanged.

Bounded recovery action in this wave is: restore the last verified runtime snapshot through `restore_integrity_state(...)`, then re-project. The projector itself does not attempt unbounded repair.

## Security boundary

- All external/provider/tool/memory/repository/browser/user content is outside the projector boundary.
- Only previously accepted typed D artifacts are consumed.
- No secret material or authority authentication key is serialized into the ledger.
- Authority references remain opaque references.
- Legacy evidence is never promoted.
- The ledger cannot issue capability grants or authorize mutations.
- Bounded text/reference constraints are inherited from contracts/evolution receipts; ledger identifiers are digests or existing bounded refs.

## Local-first profile

Projection is deterministic in-memory traversal over bounded D state. It requires no cloud service, GPU, model call, browser, repository checkout, or external index. Complexity is linear in the number of revisions for the requested goal plus deterministic hashing of bounded fields, making it suitable for the locked 8 GB local-first profile.

## Compatibility

- Existing Goal Integrity contracts remain unchanged.
- Existing v0.1 evolution receipt identities remain unchanged.
- Existing runtime schemas v1/v2/v3 remain unchanged.
- Historical DecisionReceipt schemas remain unchanged.
- Legacy restored states project truthfully using their existing provenance class.
- The ledger begins at schema version 1 and is additive/read-only.

## Fail-closed invariants

- Unknown goal: reject.
- Missing current head: reject.
- Multiple roots: reject.
- Branch, cycle, disconnected revision, self predecessor, or foreign-goal edge: reject.
- Explicit receipt missing for a revision classified as receipted: reject.
- Receipt identity, predecessor, successor, or delta mismatch: reject.
- Trust provenance class does not cover exactly every non-root revision: reject.
- Root record cannot claim evolution evidence.
- Legacy-unattested record cannot fabricate source/evidence/freshness/confidence.
- Projection never mutates runtime state.
- Reordering dictionary insertion cannot alter ledger identity.

## Initial verification matrix

Behavioral RED must call `GoalIntegrityRuntime.goal_revision_history(...)` after successfully installing a real root and verifier-authorized successor. The expected failure is absence of the public runtime method, not an import/collection error.

GREEN/adversarial coverage:

- root + verified successor produce two ordered records;
- exact source/evidence/freshness/confidence/delta/receipt lineage is preserved;
- root has no fabricated evolution provenance;
- verified, legacy-unverified, and legacy-unattested trust remain distinct;
- deterministic identity survives dictionary insertion reordering;
- unknown goal fails closed;
- malformed predecessor topology fails closed;
- tampered evolution receipt fails closed;
- projection is side-effect free;
- runtime state roundtrip reproduces the same ledger identity;
- signed authority key/secret never appears in ledger serialization;
- local-first projection performs no provider/model/network call.

## Acceptance gates

- all `tests/test_goal_design*.py` on Python 3.11 and 3.12;
- Refoundation Epoch 0 on Python 3.11 and 3.13;
- R1.9 and R2.0i integrity gates;
- latest-main race guard and exact union recompose if another specialist advances main;
- expected-head protected merge;
- actual-main post-merge Goal Design + R1.9 + R2.0i verification before CLOSED/GREEN.
