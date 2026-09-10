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
from nolane.schemas.identity import AgentStatus


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
    _git(source, "config", "user.email", "lifecycle-authority@example.invalid")
    _git(source, "config", "user.name", "Lifecycle Authority")
    (source / "README.md").write_text("lifecycle authority base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def test_completion_revalidates_sleep_authority_after_inference_before_persisting_decision(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    runtime.registry.set_status(identity.agent_id, AgentStatus.ACTIVE)
    assert runtime.registry.get(identity.agent_id).status is AgentStatus.ACTIVE

    task_id = "task-post-inference-identity-sleep-authority"
    runtime.tasks.add_task(task_id, title="identity sleep authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    workspace = _workspace(tmp_path)

    class _SleepingCompletionBackend:
        backend_id = "post-inference-identity-sleep-backend-v1"
        checkpoint_digest = "post-inference-identity-sleep-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            # SLEEPING is canonical scheduler-owned lifecycle revocation: wake()
            # must transition through WAKING before returning the agent to ACTIVE.
            # The TaskGraph lease deliberately remains intact to isolate lifecycle
            # authority drift from lease authority drift.
            assert runtime.registry.get(identity.agent_id).status is AgentStatus.ACTIVE
            runtime.registry.set_status(identity.agent_id, AgentStatus.SLEEPING)
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after identity slept during inference",
                ),
            )

    runtime.execution.bind_backend(identity.agent_id, _SleepingCompletionBackend())
    session = runtime.execution.start(
        agent_id=identity.agent_id,
        task_id=task_id,
        workspace=workspace,
        action_schema=("filesystem.read_text",),
        budget=ExecutionBudget(
            max_steps=8,
            max_tool_calls=8,
            max_external_core_calls=8,
            max_compute_units=8,
        ),
    )

    try:
        session_before = runtime.execution.get_session(session.session_id)
        execution_before = runtime.execution.to_state()
        workspace_digest_before = workspace.digest

        with pytest.raises(
            PermissionError,
            match="agent.*sleep|sleep.*agent|lifecycle.*authority|execution.*authority",
        ):
            runtime.execution.step(session.session_id)

        task = runtime.tasks.get(task_id)
        assert task.completed_by is None
        assert task.aborted_by is None
        assert task.leased_to == identity.agent_id
        assert runtime.registry.get(identity.agent_id).status is AgentStatus.SLEEPING

        assert runtime.execution.get_session(session.session_id) == session_before
        assert runtime.execution.to_state() == execution_before
        assert runtime.execution.get_session(session.session_id).decision_receipt_ids == ()
        assert runtime.execution.get_session(session.session_id).step_receipt_ids == ()
        assert runtime.execution.get_session(session.session_id).terminal_receipt_id is None
        assert runtime.execution.terminal_receipts() == ()

        assert workspace.digest == workspace_digest_before
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id
    finally:
        workspace.close()
