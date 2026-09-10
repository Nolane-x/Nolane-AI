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
    _git(source, "config", "user.email", "transient-lease-authority@example.invalid")
    _git(source, "config", "user.name", "Transient Lease Authority")
    (source / "README.md").write_text("transient lease authority base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def test_completion_rejects_transient_lease_revocation_even_after_same_agent_regrant(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = next(
        row for row in runtime.registry.identities() if row.agent_id != "nolane.central"
    )
    task_id = "task-post-inference-transient-lease-authority"
    runtime.tasks.add_task(task_id, title="transient lease authority", plan_node_id="P1")
    initial_lease = runtime.coordination.leases.grant(task_id, identity.agent_id)
    assert runtime.tasks.get(task_id).leased_to == identity.agent_id

    workspace = _workspace(tmp_path)

    class _RevokeRegrantCompletionBackend:
        backend_id = "post-inference-transient-lease-backend-v1"
        checkpoint_digest = "post-inference-transient-lease-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            current = runtime.coordination.leases.current(task_id)
            assert current.lease_id == initial_lease.lease_id
            assert current.epoch == initial_lease.epoch

            runtime.coordination.leases.revoke(
                task_id,
                "nolane.central",
                reason="revoke execution authority during inference",
            )
            replacement = runtime.coordination.leases.grant(task_id, identity.agent_id)
            assert replacement.lease_id != initial_lease.lease_id
            assert replacement.epoch > initial_lease.epoch
            assert runtime.tasks.get(task_id).leased_to == identity.agent_id

            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after lease authority was revoked and restored",
                ),
            )

    runtime.execution.bind_backend(identity.agent_id, _RevokeRegrantCompletionBackend())
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
            match="task.*lease|lease.*authority|execution.*authority|revoked.*inference",
        ):
            runtime.execution.step(session.session_id)

        task = runtime.tasks.get(task_id)
        current_lease = runtime.coordination.leases.current(task_id)
        assert task.completed_by is None
        assert task.aborted_by is None
        assert task.leased_to == identity.agent_id
        assert current_lease.agent_id == identity.agent_id
        assert current_lease.lease_id != initial_lease.lease_id
        assert current_lease.epoch > initial_lease.epoch

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
