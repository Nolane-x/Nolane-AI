from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionBudget,
    InferenceRequest,
)
from nolane.external_core.execution_workspace import RepositoryWorkspace
from nolane.external_core.integration import ChangeCandidate


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _workspace(tmp_path: Path) -> RepositoryWorkspace:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "context-authority@example.invalid")
    _git(source, "config", "user.name", "Request Bound Context Authority")
    (source / "README.md").write_text("request-bound context authority base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def test_integration_authority_change_during_inference_rejects_before_persistence(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-request-bound-context-authority-integration"
    runtime.tasks.add_task(
        task_id,
        title="request-bound integration authority",
        plan_node_id="P1",
    )
    runtime.tasks.lease(task_id, identity.agent_id)
    integration_version_before = runtime.integration.graph.version

    class _IntegrationMutatingBackend:
        backend_id = "request-bound-context-authority-backend-v1"
        checkpoint_digest = "request-bound-context-authority-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            runtime.integration.add_candidate(
                actor_agent_id="integration.chief",
                candidate=ChangeCandidate(
                    candidate_id="candidate-request-bound-context-authority",
                    producer_agent_id="integration.chief",
                    task_refs=(task_id,),
                    plan_refs=(),
                    requirement_refs=(),
                    architecture_version_expected=runtime.architecture.graph.version,
                    changed_component_refs=(),
                    changed_interface_refs=(),
                ),
            )
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.wait(
                    reason="stale integration authority decision"
                ),
            )

    runtime.execution.bind_backend(identity.agent_id, _IntegrationMutatingBackend())
    workspace = _workspace(tmp_path)
    session = runtime.execution.start(
        agent_id=identity.agent_id,
        task_id=task_id,
        workspace=workspace,
        action_schema=("filesystem.read_text",),
        budget=ExecutionBudget(
            max_steps=4,
            max_tool_calls=4,
            max_external_core_calls=4,
            max_compute_units=4,
        ),
    )

    try:
        execution_state_before = runtime.execution.to_state()
        workspace_digest_before = workspace.digest

        with pytest.raises(
            PermissionError,
            match="context.*authority|authority.*context|authoritative.*artifact",
        ):
            runtime.execution.step(session.session_id)

        assert runtime.integration.graph.version == integration_version_before + 1
        assert runtime.execution.to_state() == execution_state_before
        current = runtime.execution.get_session(session.session_id)
        assert current.step_index == 0
        assert current.counters.steps == 0
        assert current.decision_receipt_ids == ()
        assert current.step_receipt_ids == ()
        assert current.terminal_receipt_id is None
        task = runtime.tasks.get(task_id)
        assert task.leased_to == identity.agent_id
        assert task.completed_by is None
        assert task.aborted_by is None
        assert workspace.digest == workspace_digest_before
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id
    finally:
        workspace.close()
