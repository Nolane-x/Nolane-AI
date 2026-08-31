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
from nolane.external_core.execution import ExecutionSession, ExecutionState, OrganizationExecutionControlPlane
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
        raise AssertionError("recovery must never invoke the executor")

    def get_receipt(self, receipt_id: str) -> _Receipt:
        raise KeyError(receipt_id)


def _decision() -> AgentDecisionReceipt:
    schema = ("filesystem.write_text",)
    request = InferenceRequest(
        agent_id="agent-1",
        neural_version="fixture-neural-v1",
        task_id="task-agent-1",
        context_digest="context-fixture",
        encoder_version="encoder-fixture",
        checkpoint_digest="checkpoint-fixture",
        action_schema=schema,
        action_schema_digest=canonical_digest(list(schema)),
        counters=ExecutionCounters(),
        step_index=0,
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


def _session(decision: AgentDecisionReceipt) -> ExecutionSession:
    return ExecutionSession(
        session_id="execution-00000001",
        agent_id="agent-1",
        task_id="task-agent-1",
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


def test_control_recovery_rejects_idempotency_only_ownership_spoof() -> None:
    decision = _decision()
    session = _session(decision)
    protocol = ActingProtocolLedger()
    action_id = "acting-action-spoofed-owner"
    protocol.propose(
        ExecutionContract(
            action_id=action_id,
            core_id="external-api",
            operation="mutate",
            input_digest="spoofed-input-digest",
            risk_class=ExecutionRisk.R3,
            effect_class=EffectClass.EXTERNAL_MUTATION,
            required_capabilities=("capability:execute",),
            preconditions=("authorized",),
            postconditions=("outcome-evidenced",),
            idempotency_key=f"{session.session_id}:{decision.receipt_id}",
            recovery_plan="operator-guided recovery",
            budget=ActionBudget(max_attempts=1, max_external_effects=1),
        )
    )
    protocol.acquire_lease(
        action_id,
        owner_id="direct-e-client",
        authorization_ref="authorization:spoofed",
        capability_grants=("capability:execute",),
        now_ms=100,
        ttl_ms=10_000,
    )
    protocol.verify_preconditions(action_id, evidence_refs=("evidence:spoofed",), now_ms=101)
    protocol.begin_execution(action_id, now_ms=102)

    raw = _NeverInvokeExecutor()
    plane = OrganizationExecutionControlPlane(
        registry=object(),
        tasks=object(),
        context=object(),
        artifacts=object(),
        external_cores=object(),
        coding=object(),
        executor=raw,
        acting_executor=TransactionalExternalCoreExecutor(executor=raw, protocol=protocol),
        sessions=(session,),
        decisions=(decision,),
        session_counter=1,
    )

    receipts = plane.reconcile_interrupted_sessions(
        evidence_ref="recovery:restart-spoof-check",
        reason="restart must not let an unrelated E client claim an execution session",
    )

    assert receipts == ()
    assert plane.get_session(session.session_id).state is ExecutionState.RUNNING
    assert plane.get_session(session.session_id).terminal_receipt_id is None
    assert protocol.get(action_id).phase is ActionPhase.EXECUTING
    assert raw.calls == 0
