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


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _source_repo(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "workspace-attachment-authority@example.invalid")
    _git(source, "config", "user.name", "Workspace Attachment Authority")
    (source / "README.md").write_text("workspace attachment authority base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return source


def _workspace(source: Path, target: Path) -> RepositoryWorkspace:
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=target,
    )


def test_completion_rejects_transient_workspace_attachment_rebind_even_when_proof_values_match(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-post-inference-transient-workspace-attachment-authority"
    runtime.tasks.add_task(
        task_id,
        title="transient workspace attachment authority",
        plan_node_id="P1",
    )
    runtime.tasks.lease(task_id, identity.agent_id)

    source = _source_repo(tmp_path)
    original_workspace = _workspace(source, tmp_path / "workspace-original")
    replacement_workspace = _workspace(source, tmp_path / "workspace-replacement")
    assert replacement_workspace is not original_workspace
    assert replacement_workspace.root != original_workspace.root
    assert replacement_workspace.digest == original_workspace.digest
    assert replacement_workspace.execution_epoch_generation == 0

    class _WorkspaceRebindingCompletionBackend:
        backend_id = "post-inference-transient-workspace-attachment-backend-v1"
        checkpoint_digest = "post-inference-transient-workspace-attachment-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            assert session.workspace_epoch_id is not None
            assert original_workspace.active_execution_epoch_id == session.workspace_epoch_id
            assert original_workspace.active_execution_epoch_owner == session.session_id
            assert original_workspace.execution_epoch_generation == 1

            runtime.execution.attach_workspace(session.session_id, replacement_workspace)

            assert replacement_workspace.active_execution_epoch_id == session.workspace_epoch_id
            assert replacement_workspace.active_execution_epoch_owner == session.session_id
            assert replacement_workspace.execution_epoch_generation == 1
            assert replacement_workspace.digest == original_workspace.digest

            # Both workspaces can now present the same persisted epoch proof even
            # though the execution control plane changed which workspace is attached.
            assert original_workspace.active_execution_epoch_id == session.workspace_epoch_id
            assert original_workspace.active_execution_epoch_owner == session.session_id
            assert original_workspace.execution_epoch_generation == 1

            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after workspace attachment authority was rebound",
                ),
            )

    runtime.execution.bind_backend(identity.agent_id, _WorkspaceRebindingCompletionBackend())
    session = runtime.execution.start(
        agent_id=identity.agent_id,
        task_id=task_id,
        workspace=original_workspace,
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
        workspace_digest_before = original_workspace.digest
        assert session.workspace_epoch_id is not None
        assert original_workspace.execution_epoch_generation == 1
        assert replacement_workspace.execution_epoch_generation == 0

        with pytest.raises(
            PermissionError,
            match="workspace.*attachment|workspace.*authority|execution.*authority|rebound.*inference",
        ):
            runtime.execution.step(session.session_id)

        task = runtime.tasks.get(task_id)
        assert task.completed_by is None
        assert task.aborted_by is None
        assert task.leased_to == identity.agent_id

        assert runtime.execution.get_session(session.session_id) == session_before
        assert runtime.execution.to_state() == execution_before
        assert runtime.execution.get_session(session.session_id).decision_receipt_ids == ()
        assert runtime.execution.get_session(session.session_id).step_receipt_ids == ()
        assert runtime.execution.get_session(session.session_id).terminal_receipt_id is None
        assert runtime.execution.terminal_receipts() == ()

        assert original_workspace.digest == workspace_digest_before
        assert replacement_workspace.digest == workspace_digest_before
        assert replacement_workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert replacement_workspace.active_execution_epoch_owner == session.session_id
    finally:
        original_workspace.close()
        replacement_workspace.close()
