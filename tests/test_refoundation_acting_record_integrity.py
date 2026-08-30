from __future__ import annotations

import copy

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import (
    ActionBudget,
    ActingProtocolLedger,
    EffectClass,
    ExecutionContract,
    ExecutionRisk,
)


def _ready_state() -> dict[str, object]:
    contract = ExecutionContract(
        action_id="record-integrity-action",
        core_id="filesystem",
        operation="write_text",
        input_digest=canonical_digest({"path": "README.md", "content": "changed"}),
        risk_class=ExecutionRisk.R2,
        effect_class=EffectClass.LOCAL_MUTATION,
        required_capabilities=("filesystem.write",),
        preconditions=("task-lease-valid",),
        postconditions=("workspace-observed",),
        idempotency_key="record-integrity-idempotency",
        recovery_plan="restore workspace checkpoint",
        budget=ActionBudget(max_attempts=1, max_local_mutations=1, max_external_effects=0),
    )
    ledger = ActingProtocolLedger()
    ledger.propose(contract)
    ledger.acquire_lease(
        contract.action_id,
        owner_id="nolane.coder",
        authorization_ref="auth:record-integrity",
        capability_grants=contract.required_capabilities,
        now_ms=1_000,
        ttl_ms=10_000,
    )
    ledger.verify_preconditions(
        contract.action_id,
        evidence_refs=("evidence:task-lease",),
        now_ms=1_001,
    )
    return ledger.to_state()


def _recompute_local_record_digest(record: dict[str, object]) -> None:
    payload = copy.deepcopy(record)
    payload.pop("digest", None)
    record["digest"] = canonical_digest(payload)


def test_persisted_record_contract_cannot_be_rebound_even_with_local_digest_recomputed() -> None:
    state = copy.deepcopy(_ready_state())
    record = state["records"][0]
    record["contract"]["budget"]["max_local_mutations"] = 99
    _recompute_local_record_digest(record)

    with pytest.raises(ValueError, match="record contract.*event|event.*record contract"):
        ActingProtocolLedger.from_state(state)


def test_persisted_record_evidence_cannot_diverge_from_lifecycle_event() -> None:
    state = copy.deepcopy(_ready_state())
    record = state["records"][0]
    record["precondition_evidence_refs"] = ["evidence:forged"]
    _recompute_local_record_digest(record)

    with pytest.raises(ValueError, match="record.*event|event.*record"):
        ActingProtocolLedger.from_state(state)


def test_schema1_snapshot_without_record_digest_restores_and_migrates() -> None:
    state = copy.deepcopy(_ready_state())
    assert state["schema_version"] == 1
    record = state["records"][0]
    record.pop("digest")

    restored = ActingProtocolLedger.from_state(state)
    migrated = restored.to_state()

    assert migrated["schema_version"] == 1
    assert migrated["records"][0]["digest"]
    assert restored.validate_chain("record-integrity-action") is True


def test_persisted_lease_cannot_be_rebound_even_with_record_digest_recomputed() -> None:
    state = copy.deepcopy(_ready_state())
    record = state["records"][0]
    lease = record["lease"]
    lease["owner_id"] = "attacker"
    lease["expires_at_ms"] += 5_000
    _recompute_local_record_digest(record)

    with pytest.raises(ValueError, match="lease.*event|event.*lease|lease.*digest"):
        ActingProtocolLedger.from_state(state)
