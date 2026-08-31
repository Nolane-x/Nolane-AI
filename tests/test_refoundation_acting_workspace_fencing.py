from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

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
from nolane.schemas.identity import AgentStatus


class _Unused:
    def __getattr__(self, name: str):
        raise AssertionError(f"unexpected dependency access during workspace provenance validation: {name}")


@dataclass
class _Workspace:
    base_revision: str
    digest: str


@dataclass
class _Identity:
    agent_id: str = "agent-1"
    status: AgentStatus = AgentStatus.ACTIVE
    neural_version: str = "fixture-neural-v1"


@dataclass
class _Task:
    leased_to: str = "agent-1"
    aborted_by: str | None = None
    abort_reason: str | None = None


@dataclass
class _Evidence:
    artifact_id: str = "artifact-terminal-evidence"


class _Registry:
    def get(self, agent_id: str) -> _Identity:
        assert agent_id == "agent-1"
        return _Identity()


class _Tasks:
    def get(self, task_id: str) -> _Task:
        assert task_id == "task-1"
        return _Task()


class _Context:
    def compile(self, agent_id: str, *, task_id: str) -> object:
        assert agent_id == "agent-1"
        assert task_id == "task-1"
        return object()


class _Artifacts:
    def put(self, **_: Any) -> _Evidence:
        return _Evidence()


class _Encoder:
    version = "workspace-fencing-test-v1"

    def build_request(
        self,
        *,
        identity: _Identity,
        capsule: object,
        task_id: str,
        action_schema: Sequence[str],
        counters: ExecutionCounters,
        step_index: int,
        checkpoint_digest: str,
    ) -> InferenceRequest:
        del capsule
        schema = tuple(str(x) for x in action_schema)
        return InferenceRequest(
            agent_id=identity.agent_id,
            neural_version=identity.neural_version,
            task_id=task_id,
            context_digest="context-v1",
            encoder_version=self.version,
            checkpoint_digest=checkpoint_digest,
            action_schema=schema,
            action_schema_digest=canonical_digest(list(schema)),
            counters=counters,
            step_index=step_index,
        )


@dataclass
class _Backend:
    backend_id: str = "backend-v1"
    checkpoint_digest: str = "checkpoint-v1"

    def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
        return AgentDecisionReceipt.create(
            backend_id=self.backend_id,
            request=request,
            action=ExecutionAction.wait(reason="fixture wait"),
            compute_units=1,
        )


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


def _budget() -> ExecutionBudget:
    return ExecutionBudget(
        max_steps=8,
        max_tool_calls=8,
        max_external_core_calls=4,
        max_compute_units=16,
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
        budget=_budget(),
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
            "initial_workspace_digest": "workspace-current",
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
    assert roundtrip["initial_workspace_digest"] == "workspace-current"
    assert roundtrip["current_workspace_digest"] == "workspace-current"


def test_new_execution_session_mints_modern_workspace_digest_fence_at_start() -> None:
    plane = OrganizationExecutionControlPlane(
        registry=_Registry(),
        tasks=_Tasks(),
        context=_Unused(),
        artifacts=_Unused(),
        external_cores=_Unused(),
        coding=_Unused(),
        encoder=CognitiveStateEncoder(version="organization-context-digest-v1"),
        executor=object(),
        acting_executor=object(),
    )
    plane._backends["agent-1"] = _Backend()

    session = plane.start(
        agent_id="agent-1",
        task_id="task-1",
        workspace=_Workspace(base_revision="base-v1", digest="workspace-initial"),
        action_schema=("filesystem.write_text",),
        budget=_budget(),
    )

    state = session.to_state()
    assert state["workspace_provenance_version"] == 2
    assert state["initial_workspace_digest"] == "workspace-initial"
    assert state["current_workspace_digest"] == "workspace-initial"


def test_legacy_session_cannot_resume_forward_execution_by_downgrading_provenance() -> None:
    session = _session()
    plane = OrganizationExecutionControlPlane(
        registry=_Registry(),
        tasks=_Tasks(),
        context=_Context(),
        artifacts=_Artifacts(),
        external_cores=_Unused(),
        coding=_Unused(),
        encoder=_Encoder(),
        executor=object(),
        acting_executor=object(),
        sessions=(session,),
        session_counter=1,
    )
    plane._backends["agent-1"] = _Backend()
    plane.attach_workspace(
        session.session_id,
        _Workspace(base_revision="base-v1", digest="workspace-substituted"),
    )

    with pytest.raises(RuntimeError, match="legacy execution session lacks workspace provenance"):
        plane.step(session.session_id)
