from __future__ import annotations

from dataclasses import replace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import (
    ActionBudget,
    ActingProtocolLedger,
    EffectClass,
    ExecutionContract,
    ExecutionRisk,
)
from nolane.external_core.acting_runtime import TransactionalExternalCoreExecutor
from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    ExecutionStepReceipt,
    ExecutionTerminalReceipt,
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
from nolane.neural.inference_bridge import CognitiveStateEncoder


class _RawExecutor:
    external_core_ids = frozenset()

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, **_: object):
        self.calls += 1
        raise AssertionError("provenance validation must not invoke effects")

    def get_receipt(self, receipt_id: str):
        raise KeyError(receipt_id)


class _Artifacts:
    def put(self, **_: object):
        raise AssertionError("provenance preflight must fail before terminal evidence mutation")


class _Unused:
    def __getattr__(self, name: str):
        raise AssertionError(f"unexpected dependency access during provenance validation: {name}")


def _tool_action(*, operation: str = "write_text", path: str = "artifact.txt") -> ToolAction:
    arguments = {"path": path, "text": "payload"}
    return ToolAction.from_arguments("filesystem", operation, arguments)


def _decision(
    *,
    agent_id: str = "agent-1",
    step_index: int = 0,
    operation: str = "write_text",
) -> AgentDecisionReceipt:
    action_schema = ("filesystem.write_text", "filesystem.append_text")
    request = InferenceRequest(
        agent_id=agent_id,
        neural_version="fixture-neural-v1",
        task_id="task-1",
        context_digest="context-v1",
        encoder_version="organization-context-digest-v1",
        checkpoint_digest="checkpoint-v1",
        action_schema=action_schema,
        action_schema_digest=canonical_digest(list(action_schema)),
        counters=ExecutionCounters(
            steps=step_index,
            tool_calls=0,
            external_core_calls=0,
            compute_units=step_index,
        ),
        step_index=step_index,
    )
    return AgentDecisionReceipt.create(
        backend_id="backend-v1",
        request=request,
        action=ExecutionAction.tool(_tool_action(operation=operation)),
        compute_units=1,
    )


def _session(
    *,
    session_id: str = "execution-00000001",
    agent_id: str = "agent-1",
    decision_ids: tuple[str, ...] = (),
    step_ids: tuple[str, ...] = (),
    core_ids: tuple[str, ...] = (),
    terminal_id: str | None = None,
    state: ExecutionState = ExecutionState.RUNNING,
    tool_calls: int = 0,
) -> ExecutionSession:
    return ExecutionSession(
        session_id=session_id,
        agent_id=agent_id,
        task_id="task-1",
        action_schema=("filesystem.write_text", "filesystem.append_text"),
        budget=ExecutionBudget(
            max_steps=8,
            max_tool_calls=8,
            max_external_core_calls=4,
            max_compute_units=16,
        ),
        counters=ExecutionCounters(
            steps=len(decision_ids),
            tool_calls=tool_calls,
            external_core_calls=0,
            compute_units=len(decision_ids),
        ),
        step_index=len(decision_ids),
        state=state,
        backend_id="backend-v1",
        checkpoint_digest="checkpoint-v1",
        workspace_base_revision="base-v1",
        decision_receipt_ids=decision_ids,
        step_receipt_ids=step_ids,
        core_receipt_ids=core_ids,
        terminal_receipt_id=terminal_id,
    )


def _terminal(*, session: ExecutionSession, session_id: str) -> ExecutionTerminalReceipt:
    payload = {
        "session_id": session_id,
        "agent_id": session.agent_id,
        "task_id": session.task_id,
        "state": ExecutionState.FAILED.value,
        "termination_reason": "fixture failure",
        "steps": session.counters.steps,
        "tool_calls": session.counters.tool_calls,
        "external_core_calls": session.counters.external_core_calls,
        "compute_units": session.counters.compute_units,
        "wall_clock_ms": session.wall_clock_ms,
        "decision_receipt_ids": list(session.decision_receipt_ids),
        "step_receipt_ids": list(session.step_receipt_ids),
        "core_receipt_ids": list(session.core_receipt_ids),
        "output_artifact_ids": list(session.output_artifact_ids),
    }
    digest = canonical_digest(payload)
    return ExecutionTerminalReceipt(
        receipt_id="terminal-" + digest[:24],
        session_id=session_id,
        agent_id=session.agent_id,
        task_id=session.task_id,
        state=ExecutionState.FAILED,
        termination_reason="fixture failure",
        steps=session.counters.steps,
        tool_calls=session.counters.tool_calls,
        external_core_calls=session.counters.external_core_calls,
        compute_units=session.counters.compute_units,
        wall_clock_ms=session.wall_clock_ms,
        decision_receipt_ids=session.decision_receipt_ids,
        step_receipt_ids=session.step_receipt_ids,
        core_receipt_ids=session.core_receipt_ids,
        output_artifact_ids=session.output_artifact_ids,
        digest=digest,
    )


def _plane(
    *,
    sessions: tuple[ExecutionSession, ...],
    decisions: tuple[AgentDecisionReceipt, ...] = (),
    steps: tuple[ExecutionStepReceipt, ...] = (),
    terminals: tuple[ExecutionTerminalReceipt, ...] = (),
    protocol: ActingProtocolLedger | None = None,
) -> tuple[OrganizationExecutionControlPlane, _RawExecutor]:
    raw = _RawExecutor()
    acting = TransactionalExternalCoreExecutor(
        executor=raw,
        protocol=protocol or ActingProtocolLedger(),
    )
    plane = OrganizationExecutionControlPlane(
        registry=_Unused(),
        tasks=_Unused(),
        context=_Unused(),
        artifacts=_Artifacts(),
        external_cores=_Unused(),
        coding=_Unused(),
        encoder=CognitiveStateEncoder(version="organization-context-digest-v1"),
        executor=raw,
        acting_executor=acting,
        sessions=sessions,
        decisions=decisions,
        steps=steps,
        terminals=terminals,
        session_counter=max(int(row.session_id.rsplit("-", 1)[1]) for row in sessions),
    )
    return plane, raw


def test_control_plane_rejects_decision_receipt_bound_to_wrong_agent() -> None:
    decision = _decision(agent_id="agent-2")
    session = _session(decision_ids=(decision.receipt_id,))

    with pytest.raises(ValueError, match="execution decision agent binding mismatch"):
        _plane(sessions=(session,), decisions=(decision,))


def test_control_plane_rejects_step_receipt_owned_by_another_session() -> None:
    decision = _decision()
    step = ExecutionStepReceipt.create(
        session_id="execution-00000002",
        step_index=0,
        decision_receipt_id=decision.receipt_id,
        core_receipt_id="core-1",
        before_workspace_digest="before",
        after_workspace_digest="after",
        state_after=ExecutionState.RUNNING,
    )
    session = _session(
        decision_ids=(decision.receipt_id,),
        step_ids=(step.receipt_id,),
        core_ids=("core-1",),
        tool_calls=1,
    )

    with pytest.raises(ValueError, match="execution step receipt session binding mismatch"):
        _plane(sessions=(session,), decisions=(decision,), steps=(step,))


def test_control_plane_rejects_terminal_receipt_owned_by_another_session() -> None:
    decision = _decision()
    base = _session(
        decision_ids=(decision.receipt_id,),
        state=ExecutionState.FAILED,
    )
    terminal = _terminal(session=base, session_id="execution-00000002")
    session = replace(base, terminal_receipt_id=terminal.receipt_id)

    with pytest.raises(ValueError, match="execution terminal receipt session binding mismatch"):
        _plane(sessions=(session,), decisions=(decision,), terminals=(terminal,))


def test_control_plane_recovery_rejects_contract_not_semantically_bound_to_decision() -> None:
    decision = _decision(operation="write_text")
    session = _session(decision_ids=(decision.receipt_id,))
    protocol = ActingProtocolLedger()
    mismatched_action = _tool_action(operation="append_text")
    contract = ExecutionContract(
        action_id="acting-action-mismatch",
        core_id=mismatched_action.tool_id,
        operation=mismatched_action.operation,
        input_digest=canonical_digest(mismatched_action.to_state()),
        risk_class=ExecutionRisk.R2,
        effect_class=EffectClass.LOCAL_MUTATION,
        required_capabilities=("filesystem",),
        preconditions=("task-lease-valid", "tool-authorization-present"),
        postconditions=("core-outcome-evidenced",),
        idempotency_key=f"{session.session_id}:{decision.receipt_id}",
        recovery_plan="restore isolated workspace checkpoint",
        budget=ActionBudget(max_attempts=1, max_local_mutations=1, max_external_effects=0),
    )
    protocol.propose(contract)
    protocol.acquire_lease(
        contract.action_id,
        owner_id=session.agent_id,
        authorization_ref=f"decision:{decision.receipt_id}",
        capability_grants=("filesystem",),
        now_ms=100,
        ttl_ms=10_000,
    )
    protocol.verify_preconditions(
        contract.action_id,
        evidence_refs=("evidence:pre",),
        now_ms=101,
    )
    protocol.begin_execution(contract.action_id, now_ms=102)
    plane, raw = _plane(
        sessions=(session,),
        decisions=(decision,),
        protocol=protocol,
    )
    before = protocol.to_state()

    with pytest.raises(ValueError, match="acting action contract does not match bound decision"):
        plane.reconcile_interrupted_sessions(
            evidence_ref="recovery:restart-provenance",
            reason="restart with semantically mismatched acting contract",
        )

    assert protocol.to_state() == before
    assert raw.calls == 0
