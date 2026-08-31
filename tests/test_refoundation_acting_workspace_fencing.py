from __future__ import annotations

from dataclasses import dataclass

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    ExecutionStepReceipt,
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


class _Unused:
    def __getattr__(self, name: str):
        raise AssertionError(f"unexpected dependency access during workspace provenance validation: {name}")


@dataclass
class _Workspace:
    base_revision: str
    digest: str


def _decision(*, step_index: int) -> AgentDecisionReceipt:
    action_schema = ("filesystem.write_text",)
    request = InferenceRequest(
        agent_id="agent-1",
        neural_version="fixture-neural-v1",
        task_id="task-1",
        context_digest="context-v1",
        encoder_version="organization-context-digest-v1",
        checkpoint_digest="checkpoint-v1",
        action_schema=action_schema,
        action_schema_digest=canonical_digest(list(action_schema)),
        counters=ExecutionCounters(
            steps=step_index,
            tool_calls=step_index,
            external_core_calls=0,
            compute_units=step_index,
        ),
        step_index=step_index,
    )
    action = ToolAction.from_arguments(
        "filesystem",
        "write_text",
        {"path": f"artifact-{step_index}.txt", "content": f"payload-{step_index}\n"},
    )
    return AgentDecisionReceipt.create(
        backend_id="backend-v1",
        request=request,
        action=ExecutionAction.tool(action),
        compute_units=1,
    )


def _session(
    *,
    decisions: tuple[AgentDecisionReceipt, ...] = (),
    steps: tuple[ExecutionStepReceipt, ...] = (),
) -> ExecutionSession:
    return ExecutionSession(
        session_id="execution-00000001",
        agent_id="agent-1",
        task_id="task-1",
        action_schema=("filesystem.write_text",),
        budget=ExecutionBudget(
            max_steps=8,
            max_tool_calls=8,
            max_external_core_calls=4,
            max_compute_units=16,
        ),
        counters=ExecutionCounters(
            steps=len(decisions),
            tool_calls=len(steps),
            external_core_calls=0,
            compute_units=len(decisions),
        ),
        step_index=len(decisions),
        state=ExecutionState.RUNNING,
        backend_id="backend-v1",
        checkpoint_digest="checkpoint-v1",
        workspace_base_revision="base-v1",
        decision_receipt_ids=tuple(row.receipt_id for row in decisions),
        step_receipt_ids=tuple(row.receipt_id for row in steps),
        core_receipt_ids=tuple(
            row.core_receipt_id for row in steps if row.core_receipt_id is not None
        ),
    )


def _plane(
    *,
    session: ExecutionSession,
    decisions: tuple[AgentDecisionReceipt, ...] = (),
    steps: tuple[ExecutionStepReceipt, ...] = (),
) -> OrganizationExecutionControlPlane:
    return OrganizationExecutionControlPlane(
        registry=_Unused(),
        tasks=_Unused(),
        context=_Unused(),
        artifacts=_Unused(),
        external_cores=_Unused(),
        coding=_Unused(),
        encoder=CognitiveStateEncoder(version="organization-context-digest-v1"),
        executor=object(),
        acting_executor=object(),
        sessions=(session,),
        decisions=decisions,
        steps=steps,
        session_counter=1,
    )


def test_persisted_step_history_rejects_workspace_digest_discontinuity() -> None:
    decision_0 = _decision(step_index=0)
    decision_1 = _decision(step_index=1)
    step_0 = ExecutionStepReceipt.create(
        session_id="execution-00000001",
        step_index=0,
        decision_receipt_id=decision_0.receipt_id,
        core_receipt_id="core-0",
        before_workspace_digest="workspace-a",
        after_workspace_digest="workspace-b",
        state_after=ExecutionState.RUNNING,
    )
    step_1 = ExecutionStepReceipt.create(
        session_id="execution-00000001",
        step_index=1,
        decision_receipt_id=decision_1.receipt_id,
        core_receipt_id="core-1",
        before_workspace_digest="workspace-substituted",
        after_workspace_digest="workspace-c",
        state_after=ExecutionState.RUNNING,
    )
    session = _session(
        decisions=(decision_0, decision_1),
        steps=(step_0, step_1),
    )

    with pytest.raises(ValueError, match="workspace digest continuity mismatch"):
        _plane(
            session=session,
            decisions=(decision_0, decision_1),
            steps=(step_0, step_1),
        )


def test_reattach_rejects_same_revision_with_payload_mismatch_against_last_receipt() -> None:
    decision = _decision(step_index=0)
    step = ExecutionStepReceipt.create(
        session_id="execution-00000001",
        step_index=0,
        decision_receipt_id=decision.receipt_id,
        core_receipt_id="core-0",
        before_workspace_digest="workspace-a",
        after_workspace_digest="workspace-expected",
        state_after=ExecutionState.RUNNING,
    )
    session = _session(decisions=(decision,), steps=(step,))
    plane = _plane(session=session, decisions=(decision,), steps=(step,))

    with pytest.raises(ValueError, match="workspace digest"):
        plane.attach_workspace(
            session.session_id,
            _Workspace(base_revision="base-v1", digest="workspace-substituted"),
        )


def test_modern_workspace_provenance_cannot_omit_digest_fence() -> None:
    state = _session().to_state()
    state["workspace_provenance_version"] = 2

    with pytest.raises(ValueError, match="modern execution session requires workspace digest"):
        ExecutionSession.from_state(state)


def test_modern_workspace_digest_fence_survives_state_roundtrip_and_controls_reattach() -> None:
    state = _session().to_state()
    state.update(
        {
            "workspace_provenance_version": 2,
            "initial_workspace_digest": "workspace-initial",
            "current_workspace_digest": "workspace-current",
        }
    )
    session = ExecutionSession.from_state(state)
    plane = _plane(session=session)

    with pytest.raises(ValueError, match="workspace digest"):
        plane.attach_workspace(
            session.session_id,
            _Workspace(base_revision="base-v1", digest="workspace-substituted"),
        )

    plane.attach_workspace(
        session.session_id,
        _Workspace(base_revision="base-v1", digest="workspace-current"),
    )
    roundtrip = session.to_state()
    assert roundtrip["workspace_provenance_version"] == 2
    assert roundtrip["initial_workspace_digest"] == "workspace-initial"
    assert roundtrip["current_workspace_digest"] == "workspace-current"
