from __future__ import annotations

from dataclasses import dataclass

from nolane.external_core.acting_protocol import (
    ActionBudget,
    ActionPhase,
    ActingProtocolLedger,
    EffectClass,
    ExecutionContract,
    ExecutionRisk,
)
from nolane.external_core.acting_runtime import TransactionalExternalCoreExecutor


@dataclass(frozen=True)
class _Receipt:
    receipt_id: str = "unused"
    success: bool = True
    failure_kind: str | None = None
    output_artifact_ids: tuple[str, ...] = ()
    evidence_artifact_id: str = "unused-evidence"


class _NeverInvokeExecutor:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, **_: object) -> _Receipt:
        self.calls += 1
        raise AssertionError("crash reconciliation must never re-invoke a side effect")

    def get_receipt(self, receipt_id: str) -> _Receipt:
        raise KeyError(receipt_id)


def _contract(action_id: str, effect: EffectClass) -> ExecutionContract:
    risk = {
        EffectClass.READ: ExecutionRisk.R1,
        EffectClass.LOCAL_MUTATION: ExecutionRisk.R2,
        EffectClass.EXTERNAL_MUTATION: ExecutionRisk.R3,
        EffectClass.IRREVERSIBLE: ExecutionRisk.R4,
    }[effect]
    return ExecutionContract(
        action_id=action_id,
        core_id="filesystem" if effect is not EffectClass.EXTERNAL_MUTATION else "external-api",
        operation="read" if effect is EffectClass.READ else "mutate",
        input_digest=f"input:{action_id}",
        risk_class=risk,
        effect_class=effect,
        required_capabilities=("capability:execute",),
        preconditions=("authorization-still-bound",),
        postconditions=("outcome-evidenced",),
        idempotency_key=f"idempotency:{action_id}",
        recovery_plan="operator-guided recovery" if effect is EffectClass.IRREVERSIBLE else "",
        budget=ActionBudget(
            max_attempts=1,
            max_local_mutations=1 if effect is EffectClass.LOCAL_MUTATION else 0,
            max_external_effects=1 if effect in {EffectClass.EXTERNAL_MUTATION, EffectClass.IRREVERSIBLE} else 0,
        ),
    )


def _prepare(
    protocol: ActingProtocolLedger,
    action_id: str,
    effect: EffectClass,
    *,
    begin_execution: bool,
) -> None:
    protocol.propose(_contract(action_id, effect))
    protocol.acquire_lease(
        action_id,
        owner_id="agent-1",
        authorization_ref="authorization:decision-1",
        capability_grants=("capability:execute",),
        now_ms=100,
        ttl_ms=10_000,
    )
    protocol.verify_preconditions(
        action_id,
        evidence_refs=("evidence:preconditions",),
        now_ms=101,
    )
    if begin_execution:
        protocol.begin_execution(action_id, now_ms=102)


def test_pre_effect_interruption_is_cancelled_without_claiming_an_effect() -> None:
    protocol = ActingProtocolLedger()
    _prepare(protocol, "action-pre-effect", EffectClass.LOCAL_MUTATION, begin_execution=False)

    row = protocol.reconcile_interrupted(
        "action-pre-effect",
        evidence_ref="recovery:runtime-restart",
        reason="runtime restarted before effect dispatch",
    )

    assert row.phase is ActionPhase.CANCELLED
    assert row.attempts == 0
    assert row.local_mutations == 0
    assert row.external_effects == 0
    assert row.commit_ref == ""
    assert protocol.validate_chain(row.action_id)


def test_interrupted_read_execution_is_discarded_as_no_side_effect_rollback() -> None:
    protocol = ActingProtocolLedger()
    _prepare(protocol, "action-read", EffectClass.READ, begin_execution=True)

    row = protocol.reconcile_interrupted(
        "action-read",
        evidence_ref="recovery:runtime-restart",
        reason="runtime restarted while read was in flight",
    )

    assert row.phase is ActionPhase.ROLLED_BACK
    assert row.rollback_ref == "no-side-effect:recovery:runtime-restart"
    assert row.commit_ref == ""
    assert protocol.validate_chain(row.action_id)


def test_interrupted_mutating_execution_degrades_instead_of_false_rollback_or_retry() -> None:
    protocol = ActingProtocolLedger()
    _prepare(protocol, "action-local", EffectClass.LOCAL_MUTATION, begin_execution=True)

    row = protocol.reconcile_interrupted(
        "action-local",
        evidence_ref="recovery:runtime-restart",
        reason="runtime restarted after mutation dispatch",
    )

    assert row.phase is ActionPhase.DEGRADED
    assert row.rollback_ref == "recovery:runtime-restart"
    assert row.commit_ref == ""
    assert "mutation dispatch" in row.failure_reason
    assert protocol.validate_chain(row.action_id)


def test_restored_runtime_reconciles_all_inflight_actions_without_invoking_executor() -> None:
    protocol = ActingProtocolLedger()
    _prepare(protocol, "action-safe-cancel", EffectClass.LOCAL_MUTATION, begin_execution=False)
    _prepare(protocol, "action-unknown-effect", EffectClass.EXTERNAL_MUTATION, begin_execution=True)

    restored = ActingProtocolLedger.from_state(protocol.to_state())
    raw = _NeverInvokeExecutor()
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=restored)

    reconciled = kernel.reconcile_inflight(
        evidence_ref="recovery:process-restart-1",
        reason="process restart reconciliation",
    )

    assert tuple(row.action_id for row in reconciled) == (
        "action-safe-cancel",
        "action-unknown-effect",
    )
    assert restored.get("action-safe-cancel").phase is ActionPhase.CANCELLED
    assert restored.get("action-unknown-effect").phase is ActionPhase.DEGRADED
    assert raw.calls == 0

    assert kernel.reconcile_inflight(
        evidence_ref="recovery:process-restart-2",
        reason="second reconciliation is a no-op",
    ) == ()
    assert raw.calls == 0
