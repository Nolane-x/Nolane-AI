from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.execution import ExecutionStepReceipt
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionBudget,
    InferenceRequest,
)
from nolane.external_core.execution_workspace import RepositoryWorkspace


class _RecordingBackend:
    backend_id = "decision-lineage-backend-v1"
    checkpoint_digest = "decision-lineage-checkpoint-v1"

    def __init__(self) -> None:
        self.requests: list[InferenceRequest] = []

    def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
        self.requests.append(request)
        return AgentDecisionReceipt.create(
            backend_id=self.backend_id,
            request=request,
            action=ExecutionAction.wait(reason="lineage fixture"),
        )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _workspace(tmp_path: Path, name: str) -> RepositoryWorkspace:
    source = tmp_path / f"source-{name}"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "decision-lineage@example.invalid")
    _git(source, "config", "user.name", "Decision Lineage")
    (source / "README.md").write_text("decision lineage base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / f"workspace-{name}",
    )


def _runtime_with_two_sessions(tmp_path: Path):
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-decision-lineage"
    runtime.tasks.add_task(task_id, title="decision lineage", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)
    backend = _RecordingBackend()
    runtime.execution.bind_backend(identity.agent_id, backend)
    budget = ExecutionBudget(
        max_steps=8,
        max_tool_calls=8,
        max_external_core_calls=8,
        max_compute_units=8,
    )
    workspace_a = _workspace(tmp_path, "a")
    workspace_b = _workspace(tmp_path, "b")
    session_a = runtime.execution.start(
        agent_id=identity.agent_id,
        task_id=task_id,
        workspace=workspace_a,
        action_schema=("wait",),
        budget=budget,
    )
    session_b = runtime.execution.start(
        agent_id=identity.agent_id,
        task_id=task_id,
        workspace=workspace_b,
        action_schema=("wait",),
        budget=budget,
    )
    return runtime, backend, session_a, session_b, workspace_a, workspace_b


def test_modern_inference_request_is_bound_to_execution_session_and_epoch(tmp_path: Path) -> None:
    runtime, backend, session_a, _session_b, workspace_a, workspace_b = _runtime_with_two_sessions(tmp_path)
    try:
        runtime.execution.step(session_a.session_id)
        request = backend.requests[-1]
        assert request.execution_lineage_version == 2
        assert request.execution_session_id == session_a.session_id
        assert request.workspace_epoch_id == session_a.workspace_epoch_id
    finally:
        workspace_a.close()
        workspace_b.close()


def test_restore_rejects_canonical_decision_transplant_between_execution_sessions(tmp_path: Path) -> None:
    runtime, _backend, session_a, session_b, workspace_a, workspace_b = _runtime_with_two_sessions(tmp_path)
    try:
        step_a = runtime.execution.step(session_a.session_id)
        runtime.execution.step(session_b.session_id)
        state = runtime.to_state()

        execution_state = state["execution"]
        sessions = {row["session_id"]: row for row in execution_state["sessions"]}
        decisions = {row["receipt_id"]: row for row in execution_state["decisions"]}
        session_a_state = dict(sessions[session_a.session_id])
        session_b_state = sessions[session_b.session_id]
        decision_b_id = session_b_state["decision_receipt_ids"][0]
        decision_b = decisions[decision_b_id]

        assert isinstance(step_a, ExecutionStepReceipt)
        transplanted_step = ExecutionStepReceipt.create(
            session_id=session_a.session_id,
            step_index=step_a.step_index,
            decision_receipt_id=decision_b_id,
            core_receipt_id=step_a.core_receipt_id,
            before_workspace_digest=step_a.before_workspace_digest,
            after_workspace_digest=step_a.after_workspace_digest,
            state_after=step_a.state_after,
            output_artifact_ids=step_a.output_artifact_ids,
            core_contract_digest=step_a.core_contract_digest,
            workspace_epoch_id=step_a.workspace_epoch_id,
        )
        session_a_state["decision_receipt_ids"] = [decision_b_id]
        session_a_state["step_receipt_ids"] = [transplanted_step.receipt_id]
        execution_state["sessions"] = [session_a_state]
        execution_state["decisions"] = [decision_b]
        execution_state["steps"] = [transplanted_step.to_state()]
        execution_state["request_provenance_decision_ids"] = [decision_b_id]
        if "context_provenance_decision_ids" in execution_state:
            execution_state["context_provenance_decision_ids"] = [decision_b_id]

        with pytest.raises(ValueError, match="execution session|workspace epoch|lineage"):
            OrganizationRuntime.from_state(state)
    finally:
        workspace_a.close()
        workspace_b.close()
