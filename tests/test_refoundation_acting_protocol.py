from __future__ import annotations

import copy

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import (
    ActionBudget,
    ActionPhase,
    ActingProtocolLedger,
    EffectClass,
    ExecutionContract,
    ExecutionRisk,
    IdempotencyConflict,
    LeaseExpired,
    ProtocolViolation,
    VerifierLevel,
)


def _contract(
    action_id: str = "action-1",
    *,
    key: str = "idem-1",
    risk: ExecutionRisk = ExecutionRisk.R2,
    effect: EffectClass = EffectClass.LOCAL_MUTATION,
    capabilities: tuple[str, ...] = ("filesystem.write",),
    recovery_plan: str = "restore workspace checkpoint",
    budget: ActionBudget | None = None,
) -> ExecutionContract:
    return ExecutionContract(
        action_id=action_id,
        core_id="filesystem",
        operation="write_text",
        input_digest=canonical_digest({"path": "README.md", "content": "changed"}),
        risk_class=risk,
        effect_class=effect,
        required_capabilities=capabilities,
        preconditions=("task-lease-valid", "mutation-scope-covered"),
        postconditions=("workspace-observed", "receipt-persisted"),
        idempotency_key=key,
        recovery_plan=recovery_plan,
        budget=budget or ActionBudget(max_attempts=2, max_local_mutations=2, max_external_effects=1),
    )


def _ready(ledger: ActingProtocolLedger, contract: ExecutionContract, *, now: int = 1_000) -> None:
    ledger.propose(contract)
    ledger.acquire_lease(
        contract.action_id,
        owner_id="nolane.coder",
        authorization_ref="auth:decision-1",
        capability_grants=contract.required_capabilities,
        now_ms=now,
        ttl_ms=10_000,
    )
    ledger.verify_preconditions(
        contract.action_id,
        evidence_refs=("evidence:task-lease", "evidence:claim"),
        now_ms=now + 1,
    )


def test_commit_requires_postcondition_gate_and_receipt_chain() -> None:
    ledger = ActingProtocolLedger()
    contract = _contract()
    _ready(ledger, contract)

    ledger.begin_execution(contract.action_id, now_ms=1_002)
    ledger.observe_outcome(contract.action_id, outcome_ref="core:receipt-1", success=True, now_ms=1_003)

    with pytest.raises(ProtocolViolation, match="postcondition"):
        ledger.commit(contract.action_id, commit_ref="commit:1", now_ms=1_004)

    ledger.verify_postconditions(
        contract.action_id,
        evidence_refs=("verify:workspace", "verify:receipt"),
        verifier_level=VerifierLevel.V2,
        now_ms=1_004,
    )
    committed = ledger.commit(contract.action_id, commit_ref="commit:1", now_ms=1_005)

    assert committed.phase is ActionPhase.COMMITTED
    assert ledger.validate_chain(contract.action_id) is True
    assert [event.sequence for event in ledger.events(contract.action_id)] == list(range(len(ledger.events(contract.action_id))))


def test_expired_lease_blocks_forward_execution_but_recovery_remains_possible() -> None:
    ledger = ActingProtocolLedger()
    contract = _contract()
    ledger.propose(contract)
    ledger.acquire_lease(
        contract.action_id,
        owner_id="nolane.coder",
        authorization_ref="auth:decision-1",
        capability_grants=contract.required_capabilities,
        now_ms=100,
        ttl_ms=5,
    )

    with pytest.raises(LeaseExpired):
        ledger.verify_preconditions(contract.action_id, evidence_refs=("evidence:pre",), now_ms=106)

    cancelled = ledger.cancel(contract.action_id, reason="lease expired before effects", evidence_ref="recovery:no-effects")
    assert cancelled.phase is ActionPhase.CANCELLED


def test_idempotency_replay_returns_original_record_and_collision_is_rejected() -> None:
    ledger = ActingProtocolLedger()
    first = ledger.propose(_contract(action_id="action-original", key="stable-key"))
    replay = ledger.propose(_contract(action_id="action-retry", key="stable-key"))

    assert replay.action_id == first.action_id == "action-original"
    assert len(ledger.records()) == 1

    conflicting = ExecutionContract(
        **{
            **_contract(action_id="action-conflict", key="stable-key").to_state(),
            "operation": "append_text",
        }
    )
    with pytest.raises(IdempotencyConflict):
        ledger.propose(conflicting)


def test_capability_and_effect_budget_are_enforced_before_execution() -> None:
    ledger = ActingProtocolLedger()
    contract = _contract(
        budget=ActionBudget(max_attempts=1, max_local_mutations=0, max_external_effects=0),
    )
    ledger.propose(contract)

    with pytest.raises(PermissionError, match="capabilit"):
        ledger.acquire_lease(
            contract.action_id,
            owner_id="nolane.coder",
            authorization_ref="auth:decision-1",
            capability_grants=(),
            now_ms=100,
            ttl_ms=100,
        )

    ledger.acquire_lease(
        contract.action_id,
        owner_id="nolane.coder",
        authorization_ref="auth:decision-1",
        capability_grants=contract.required_capabilities,
        now_ms=100,
        ttl_ms=100,
    )
    ledger.verify_preconditions(contract.action_id, evidence_refs=("evidence:pre",), now_ms=101)
    with pytest.raises(ProtocolViolation, match="local mutation budget"):
        ledger.begin_execution(contract.action_id, now_ms=102)


def test_high_risk_actions_require_recovery_and_stronger_postcondition_verification() -> None:
    with pytest.raises(ValueError, match="recovery plan"):
        _contract(risk=ExecutionRisk.R4, effect=EffectClass.IRREVERSIBLE, recovery_plan="")

    ledger = ActingProtocolLedger()
    contract = _contract(risk=ExecutionRisk.R4, effect=EffectClass.IRREVERSIBLE)
    _ready(ledger, contract)
    ledger.begin_execution(contract.action_id, now_ms=1_002)
    ledger.observe_outcome(contract.action_id, outcome_ref="core:receipt-r4", success=True, now_ms=1_003)

    with pytest.raises(PermissionError, match="V4"):
        ledger.verify_postconditions(
            contract.action_id,
            evidence_refs=("verify:weak",),
            verifier_level=VerifierLevel.V2,
            now_ms=1_004,
        )

    verified = ledger.verify_postconditions(
        contract.action_id,
        evidence_refs=("verify:independent-v4",),
        verifier_level=VerifierLevel.V4,
        now_ms=1_004,
    )
    assert verified.phase is ActionPhase.POSTCONDITION_VERIFIED


def test_failed_effect_can_rollback_without_false_commit() -> None:
    ledger = ActingProtocolLedger()
    contract = _contract()
    _ready(ledger, contract)
    ledger.begin_execution(contract.action_id, now_ms=1_002)
    ledger.observe_outcome(contract.action_id, outcome_ref="core:failed", success=False, now_ms=1_003)
    rolled = ledger.rollback(
        contract.action_id,
        rollback_ref="workspace:checkpoint-restored",
        failure_reason="core execution failed",
    )

    assert rolled.phase is ActionPhase.ROLLED_BACK
    assert rolled.commit_ref == ""
    with pytest.raises(ProtocolViolation):
        ledger.commit(contract.action_id, commit_ref="must-not-commit", now_ms=1_004)


def test_state_roundtrip_validates_receipt_chain_and_rejects_tampering() -> None:
    ledger = ActingProtocolLedger()
    contract = _contract()
    _ready(ledger, contract)
    state = ledger.to_state()

    restored = ActingProtocolLedger.from_state(state)
    assert restored.to_state() == state
    assert restored.validate_chain(contract.action_id)

    tampered = copy.deepcopy(state)
    tampered["events"][0]["digest"] = "0" * 64
    with pytest.raises(ValueError, match="event digest"):
        ActingProtocolLedger.from_state(tampered)
