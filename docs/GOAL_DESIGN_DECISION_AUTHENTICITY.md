# D. Goal / Design — Decision Authenticity and Ledger Binding

## Purpose

Goal/Design decision authority is not established by possession of a `receipt_id` alone. A downstream consumer must be able to prove that the receipt body is exactly the content that was admitted and that the authority event referenced by the decision index is the exact typed ledger event that authorized that receipt.

This hardening layer closes the gap between content-addressed minting, persistence, in-memory ownership, and later authority consumption.

## Authority invariants

1. **Receipt identity is semantic identity.** Mutating any identity-bearing receipt field while retaining the old `receipt_id` is rejected.
2. **Historical receipts remain verifiable.** Legacy v1 receipts retain their original eight-field identity scheme.
3. **Historical ledger events remain verifiable.** A v1 receipt accepts the pre-manifest DECISION-event payload that existed before manifest-aware authority events were introduced.
4. **The known transitional v1 event remains verifiable.** A genuine v1 receipt may also be paired with the exact historical transitional event payload that included `input_manifest_digest=""`; no other hybrid event schema is accepted.
5. **Current receipts use complete manifests.** v2 receipts bind the seven Goal/Design semantic/state digests in addition to the v1 fields.
6. **No implicit hybrid receipt schema.** If any v2 manifest field is populated, all seven must be populated; partial v2 state fails closed.
7. **Ledger minting cannot launder a forged receipt.** `GoalDesignLedger.record_decision()` verifies receipt authenticity before creating an `AUTHORITY` event.
8. **Index identity cannot be rebound.** `DecisionAuthorityIndex.register()` and persistence restore verify receipt identity before accepting the record.
9. **The authority index owns its receipt state.** Mutable members of a caller-owned `DecisionReceipt`, including `version_vector`, are defensively copied on ingress and on egress. Mutating the original receipt or a returned record cannot mutate indexed authority in place.
10. **Authority-event references are proofs, not labels.** `validate_ledger_binding()` requires the referenced event to exist and to be exactly `DECISION + AUTHORITY` with canonical receipt-bound payload and subjects.
11. **Persistence loading is distinct from authority trust.** An index may be deserialized independently, but consumers must pair it with its ledger and validate the binding before trusting restored authority.
12. **D owns decision authority.** This layer does not change E. Acting transaction semantics. Execution may consume D authority, but it does not mint or reinterpret it.

## Receipt identity versions

### v1 — historical identity

The original receipt identity is the SHA-256 stable digest of:

- `goal_id`
- `selected_option_id`
- `snapshot_digest`
- `version_vector`
- `evaluation_digest`
- `proof_obligation_ids`
- `uncertainty_ids`
- `evidence_refs`

A receipt whose seven extended manifest fields are all empty is verified against this identity.

### v2 — proof-carrying identity

Current receipts add:

- `goal_digest`
- `scenario_set_digest`
- `option_set_digest`
- `proof_state_digest`
- `uncertainty_state_digest`
- `traceability_digest`
- `input_manifest_digest`

All seven are required together. This avoids silently inventing unversioned intermediate identity schemes.

## Decision-event payload generations

Receipt and ledger-event compatibility must move together. The historical ledger used this canonical payload for v1 receipts:

```text
receipt_id
goal_id
selected_option_id
snapshot_digest
evaluation_digest
```

During the migration to manifest-aware events, a v1 receipt could also have been written with the same payload plus an explicitly empty:

```text
input_manifest_digest = ""
```

That exact transitional shape remains recognized for historical verification. It is not a general hybrid escape hatch.

Manifest-aware v2 receipts use the same payload plus a non-empty authenticated:

```text
input_manifest_digest
```

The verifier derives the event generation from the authenticated receipt itself. A caller cannot select the weaker v1 event schema for a v2 receipt, and a historical v1 event is not invalidated merely because the current runtime knows about manifest digests.

## Exact authority-event binding

For an indexed receipt `R`, the referenced ledger event must prove all of the following:

```text
event.kind            == DECISION
event.authority_level == AUTHORITY
event.payload_digest  ∈ accepted_payload_digests(R)
event.subject_refs    == (R.goal_id, R.selected_option_id, R.snapshot_digest)
```

For v2 there is exactly one accepted current payload digest. For v1 the accepted set contains only the canonical pre-manifest payload and the exact known transitional empty-manifest payload.

A content-addressed event with valid internal structure but different semantic kind, authority level, payload, or subjects cannot substitute for the original authority event.

## In-memory authority ownership

`DecisionReceipt` is a frozen dataclass, but a mapping stored inside it can still be mutable. Therefore `frozen=True` alone is not a sufficient authority boundary.

`DecisionAuthorityIndex` treats receipts as externally supplied values and establishes private ownership:

```text
caller receipt
    │
    │ defensive copy on register/restore
    ▼
private indexed receipt
    │
    │ defensive copy on get/records/lifecycle return
    ▼
consumer-visible receipt
```

The index never relies on caller discipline to preserve the body that was authenticated. This prevents a valid receipt from being registered and then silently rewritten through a retained `version_vector` alias.

## Trust pipeline

```text
Goal/Design admission
        │
        ▼
content-addressed DecisionReceipt
        │  verify_decision_receipt()
        ▼
typed GoalDesignLedger.record_decision()
        │
        ▼
version-matched DECISION + AUTHORITY event
        │
        ▼
DecisionAuthorityIndex.register()
        │  private receipt ownership
        ▼
persist / restart / restore
        │
        ▼
DecisionAuthorityIndex.validate_ledger_binding(ledger)
        │
        ▼
trusted D authority for downstream consumption
```

## Threat and compatibility cases covered by tests

The Goal/Design test suite explicitly rejects:

- receipt body mutation under an unchanged ID,
- tampered persisted receipt body,
- forged receipt presented to ledger authority minting,
- missing indexed authority event,
- semantically forged event even when its own content-addressed event ID is recomputed,
- partially populated v2 manifest state,
- mutation of indexed authority through caller-held or consumer-visible mapping aliases.

It also proves the compatibility layers:

- a legitimate legacy v1 receipt remains authentic and admissible;
- a legitimate pre-manifest v1 DECISION authority event remains jointly verifiable with that receipt;
- the exact known transitional v1 event with an empty manifest field remains jointly verifiable;
- current v2 receipts require the complete proof-carrying manifest and cannot downgrade to v1 semantics.

## Ownership boundary

The authenticity verifier is implemented in `nolane/external_core/goal_design_authenticity.py` and is consumed by D's ledger and authority index. It deliberately does not import or modify Acting runtime behavior. This keeps the contract directional:

```text
D. Goal / Design  ──issues/proves authority──►  downstream execution
```

rather than allowing execution code to redefine design authority.
