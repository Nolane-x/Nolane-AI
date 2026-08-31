# D. Goal / Design — Decision Authenticity and Ledger Binding

## Purpose

Goal/Design decision authority is not established by possession of a `receipt_id` alone. A downstream consumer must be able to prove that the receipt body is exactly the content that was admitted and that the authority event referenced by the decision index is the exact typed ledger event that authorized that receipt.

This hardening layer closes the gap between content-addressed minting, persistence, and later authority consumption.

## Authority invariants

1. **Receipt identity is semantic identity.** Mutating any identity-bearing receipt field while retaining the old `receipt_id` is rejected.
2. **Historical receipts remain verifiable.** Legacy v1 receipts retain their original eight-field identity scheme.
3. **Current receipts use complete manifests.** v2 receipts bind the seven Goal/Design semantic/state digests in addition to the v1 fields.
4. **No implicit hybrid schema.** If any v2 manifest field is populated, all seven must be populated; partial v2 state fails closed.
5. **Ledger minting cannot launder a forged receipt.** `GoalDesignLedger.record_decision()` verifies receipt authenticity before creating an `AUTHORITY` event.
6. **Index identity cannot be rebound.** `DecisionAuthorityIndex.register()` and persistence restore verify receipt identity before accepting the record.
7. **Authority-event references are proofs, not labels.** `validate_ledger_binding()` requires the referenced event to exist and to be exactly `DECISION + AUTHORITY` with canonical receipt-bound payload and subjects.
8. **Persistence loading is distinct from authority trust.** An index may be deserialized independently, but consumers must pair it with its ledger and validate the binding before trusting restored authority.
9. **D owns decision authority.** This layer does not change E. Acting transaction semantics. Execution may consume D authority, but it does not mint or reinterpret it.

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

## Exact authority-event binding

For an indexed receipt `R`, the referenced ledger event must prove all of the following:

```text
event.kind            == DECISION
event.authority_level == AUTHORITY
event.payload_digest  == digest(canonical_decision_event_payload(R))
event.subject_refs    == (R.goal_id, R.selected_option_id, R.snapshot_digest)
```

The canonical event payload includes:

- receipt ID,
- goal ID,
- selected option ID,
- snapshot digest,
- evaluation digest,
- input manifest digest.

A content-addressed event with valid internal structure but different semantic kind, authority level, payload, or subjects cannot substitute for the original authority event.

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
DECISION + AUTHORITY event
        │
        ▼
DecisionAuthorityIndex.register()
        │
        ▼
persist / restart / restore
        │
        ▼
DecisionAuthorityIndex.validate_ledger_binding(ledger)
        │
        ▼
trusted D authority for downstream consumption
```

## Threat cases covered by tests

The Goal/Design test suite explicitly rejects:

- receipt body mutation under an unchanged ID,
- tampered persisted receipt body,
- forged receipt presented to ledger authority minting,
- missing indexed authority event,
- semantically forged event even when its own content-addressed event ID is recomputed,
- partially populated v2 manifest state.

It also proves that a legitimate legacy v1 receipt remains admissible and can be bound to an exact authority event.

## Ownership boundary

The authenticity verifier is implemented in `nolane/external_core/goal_design_authenticity.py` and is consumed by D's ledger and authority index. It deliberately does not import or modify Acting runtime behavior. This keeps the contract directional:

```text
D. Goal / Design  ──issues/proves authority──►  downstream execution
```

rather than allowing execution code to redefine design authority.
