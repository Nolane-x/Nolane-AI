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


def _workspace(tmp_path: Path) -> RepositoryWorkspace:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "transient-workspace-epoch@example.invalid")
    _git(source, "config", "user.name", "Transient Workspace Epoch")
    (source / "README.md").write_text("transient workspace epoch base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def test_completion_rejects_transient_workspace_epoch_revocation_even_after_same_epoch_is_reclaimed(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-post-inference-transient-workspace-epoch-authority"
    runtime.tasks.add_task(task_id, title="transient workspace epoch authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)
    workspace = _workspace(tmp_path)

    class _ReleaseReclaimCompletionBackend:
        backend_id = "post-inference-transient-workspace-epoch-backend-v1"
        checkpoint_digest = "post-inference-transient-workspace-epoch-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            assert session.workspace_epoch_id is not None
            assert workspace.active_execution_epoch_id == session.workspace_epoch_id
            assert workspace.active_execution_epoch_owner == session.session_id

            workspace.release_execution_epoch(
                session.session_id,
                session.workspace_epoch_id,
            )
            assert workspace.active_execution_epoch_id is None
            assert workspace.active_execution_epoch_owner is None

            reclaimed_epoch_id = workspace.claim_execution_epoch(
                session.session_id,
                expected_epoch_id=session.workspace_epoch_id,
            )
            assert reclaimed_epoch_id == session.workspace_epoch_id
            assert workspace.active_execution_epoch_id == session.workspace_epoch_id
            assert workspace.active_execution_epoch_owner == session.session_id

            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after workspace epoch authority was revoked and restored",
                ),
            )

    runtime.execution.bind_backend(identity.agent_id, _ReleaseReclaimCompletionBackend())
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
        assert session.workspace_epoch_id is not None
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id

        with pytest.raises(
            PermissionError,
            match="workspace.*epoch|epoch.*authority|execution.*authority|revoked.*inference",
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

        assert workspace.digest == workspace_digest_before
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id
    finally:
        workspace.close()
