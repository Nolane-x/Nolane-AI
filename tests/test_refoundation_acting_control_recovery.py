from __future__ import annotations

from dataclasses import dataclass

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import (
    ActionBudget,
    ActionPhase,
    ActingProtocolLedger,
    EffectClass,
    ExecutionContract,
    ExecutionRisk,
)
from nolane.external_core.acting_runtime import TransactionalExternalCoreExecutor
from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    OrganizationExecutionControlPlane,
)
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionBudget,
    ExecutionCounters,
    InferenceRequest,
    ToolAction,
)


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
        raise AssertionError("control-plane recovery must never invoke a tool/core")

    def get_receipt(self, receipt_id: str) -> _Receipt:
        raise KeyError(receipt_id)


def _decision(*, agent_id: str, step_index: int) -> AgentDecisionReceipt:
    schema = ("filesystem.write_text",)
    request = InferenceRequest(
        agent_id=agent_id,
        neural_version="fixture-neural-v1",
        task_id=f"task-{agent_id}",
        context_digest="context-fixture",
        encoder_version="encoder-fixture",
        checkpoint_digest="checkpoint-fixture",
        action_schema=schema,
        action_schema_digest=canonical_digest(list(schema)),
        counters=ExecutionCounters(),
        step_index=step_index,
    )
    return AgentDecisionReceipt.create(
        backend_id="backend-fixture",
        request=request,
        action=ExecutionAction.tool(
            ToolAction.from_arguments(
                "filesystem",
                "write_text",
                {"path": "README.md", "content": "changed\n"},
            )
        ),
        compute_units=1,
    )


def _session(*, session_id: str, agent_id: str, decision: AgentDecisionReceipt) -> ExecutionSession:
    return ExecutionSession(
        session_id=session_id,
        agent_id=agent_id,
        task_id=f"task-{agent_id}",
        action_schema=("filesystem.write_text",),
        budget=ExecutionBudget(
            max_steps=8,
            max_tool_calls=4,
            max_external_core_calls=2,
            max_compute_units=8,
        ),
        counters=ExecutionCounters(steps=1, compute_units=1),
        step_index=1,
        state=ExecutionState.RUNNING,
        backend_id="backend-fixture",
        checkpoint_digest="checkpoint-fixture",
        workspace_base_revision="base-fixture",
        decision_receipt_ids=(decision.receipt_id,),
    )


def _prepare_action(
    protocol: ActingProtocolLedger,
    *,
    action_id: str,
    idempotency_key: str,
    effect: EffectClass,
    begin_execution: bool,
) -> None:
    risk = {
        EffectClass.READ: ExecutionRisk.R1,
        EffectClass.LOCAL_MUTATION: ExecutionRisk.R2,
        EffectClass.EXTERNAL_MUTATION: ExecutionRisk.R3,
        EffectClass.IRREVERSIBLE: ExecutionRisk.R4,
    }[effect]
    protocol.propose(
        ExecutionContract(
            action_id=action_id,
            core_id="filesystem" if effect is not EffectClass.EXTERNAL_MUTATION else "external-api",
            operation="mutate",
            input_digest=f"input:{action_id}",
            risk_class=risk,
            effect_class=effect,
            required_capabilities=("capability:execute",),
            preconditions=("authorized",),
            postconditions=("outcome-evidenced",),
            idempotency_key=idempotency_key,
            recovery_plan="operator-guided recovery" if effect is EffectClass.IRREVERSIBLE else "",
            budget=ActionBudget(
                max_attempts=1,
                max_local_mutations=1 if effect is EffectClass.LOCAL_MUTATION else 0,
                max_external_effects=1 if effect in {EffectClass.EXTERNAL_MUTATION, EffectClass.IRREVERSIBLE} else 0,
            ),
        )
    )
    protocol.acquire_lease(
        action_id,
        owner_id="agent-owner",
        authorization_ref="authorization:decision",
        capability_grants=("capability:execute",),
        now_ms=100,
        ttl_ms=10_000,
    )
    protocol.verify_preconditions(
        action_id,
        evidence_refs=("evidence:authorized",),
        now_ms=101,
    )
    if begin_execution:
        protocol.begin_execution(action_id, now_ms=102)


def _plane(
    *,
    protocol: ActingProtocolLedger,
    sessions: tuple[ExecutionSession, ...],
    decisions: tuple[AgentDecisionReceipt, ...],
) -> tuple[OrganizationExecutionControlPlane, _NeverInvokeExecutor]:
    raw = _NeverInvokeExecutor()
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)
    plane = OrganizationExecutionControlPlane(
        registry=object(),
        tasks=object(),
        context=object(),
        artifacts=object(),
        external_cores=object(),
        coding=object(),
        executor=raw,
        acting_executor=kernel,
        sessions=sessions,
        decisions=decisions,
        session_counter=len(sessions),
    )
    return plane, raw


def test_control_recovery_targets_only_owned_action_and_fails_degraded_session() -> None:
    protocol = ActingProtocolLedger()
    owned_decision = _decision(agent_id="agent-1", step_index=0)
    unaffected_decision = _decision(agent_id="agent-2", step_index=0)
    owned = _session(session_id="execution-00000001", agent_id="agent-1", decision=owned_decision)
    unaffected = _session(session_id="execution-00000002", agent_id="agent-2", decision=unaffected_decision)

    _prepare_action(
        protocol,
        action_id="acting-action-owned",
        idempotency_key=f"{owned.session_id}:{owned_decision.receipt_id}",
        effect=EffectClass.EXTERNAL_MUTATION,
        begin_execution=True,
    )
    _prepare_action(
        protocol,
        action_id="acting-action-direct-client",
        idempotency_key="direct-e-client:opaque-operation",
        effect=EffectClass.LOCAL_MUTATION,
        begin_execution=True,
    )

    plane, raw = _plane(
        protocol=protocol,
        sessions=(owned, unaffected),
        decisions=(owned_decision, unaffected_decision),
    )

    receipts = plane.reconcile_interrupted_sessions(
        evidence_ref="recovery:process-restart-42",
        reason="process restarted with an interrupted acting transaction",
    )

    assert len(receipts) == 1
    terminal = receipts[0]
    assert terminal.session_id == owned.session_id
    assert terminal.state is ExecutionState.FAILED
    assert "acting-action-owned" in terminal.termination_reason
    assert ActionPhase.DEGRADED.value in terminal.termination_reason
    assert "recovery:process-restart-42" in terminal.termination_reason
    assert plane.get_session(owned.session_id).terminal_receipt_id == terminal.receipt_id
    assert plane.get_session(unaffected.session_id).state is ExecutionState.RUNNING
    assert plane.get_session(unaffected.session_id).terminal_receipt_id is None
    assert protocol.get("acting-action-owned").phase is ActionPhase.DEGRADED
    assert protocol.get("acting-action-direct-client").phase is ActionPhase.EXECUTING
    assert raw.calls == 0


def test_control_recovery_aborts_safe_pre_effect_interruption_and_is_idempotent() -> None:
    protocol = ActingProtocolLedger()
    decision = _decision(agent_id="agent-1", step_index=0)
    session = _session(session_id="execution-00000001", agent_id="agent-1", decision=decision)
    _prepare_action(
        protocol,
        action_id="acting-action-pre-effect",
        idempotency_key=f"{session.session_id}:{decision.receipt_id}",
        effect=EffectClass.LOCAL_MUTATION,
        begin_execution=False,
    )
    plane, raw = _plane(protocol=protocol, sessions=(session,), decisions=(decision,))

    first = plane.reconcile_interrupted_sessions(
        evidence_ref="recovery:restart-safe",
        reason="restart happened before effect dispatch",
    )

    assert len(first) == 1
    assert first[0].state is ExecutionState.ABORTED
    assert ActionPhase.CANCELLED.value in first[0].termination_reason
    assert protocol.get("acting-action-pre-effect").phase is ActionPhase.CANCELLED
    terminal_ids = tuple(row.receipt_id for row in plane.terminal_receipts())

    second = plane.reconcile_interrupted_sessions(
        evidence_ref="recovery:restart-safe-again",
        reason="second recovery must be a no-op",
    )

    assert second == ()
    assert tuple(row.receipt_id for row in plane.terminal_receipts()) == terminal_ids
    assert raw.calls == 0


def test_runtime_reconcile_filter_never_mutates_unselected_inflight_actions() -> None:
    protocol = ActingProtocolLedger()
    _prepare_action(
        protocol,
        action_id="acting-action-selected",
        idempotency_key="execution-00000001:decision-selected",
        effect=EffectClass.LOCAL_MUTATION,
        begin_execution=True,
    )
    _prepare_action(
        protocol,
        action_id="acting-action-unselected",
        idempotency_key="direct-client:unselected",
        effect=EffectClass.EXTERNAL_MUTATION,
        begin_execution=True,
    )
    raw = _NeverInvokeExecutor()
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)

    rows = kernel.reconcile_inflight(
        evidence_ref="recovery:filtered",
        reason="only the selected owner is recovering",
        action_ids=("acting-action-selected",),
    )

    assert tuple(row.action_id for row in rows) == ("acting-action-selected",)
    assert protocol.get("acting-action-selected").phase is ActionPhase.DEGRADED
    assert protocol.get("acting-action-unselected").phase is ActionPhase.EXECUTING
    assert raw.calls == 0
