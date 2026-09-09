from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.execution_types import ExecutionAction, ExecutionBudget
from nolane.external_core.execution_workspace import RepositoryWorkspace
from nolane.neural.inference_bridge import DeterministicFixtureBackend


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _workspace(root: Path) -> RepositoryWorkspace:
    source = root / "source"
    source.mkdir(parents=True)
    _git(source, "init")
    _git(source, "config", "user.email", "active-session-authority@example.invalid")
    _git(source, "config", "user.name", "Active Session Authority")
    (source / "README.md").write_text("active session authority\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=root / "workspace",
    )


def _budget() -> ExecutionBudget:
    return ExecutionBudget(
        max_steps=8,
        max_tool_calls=8,
        max_external_core_calls=8,
        max_compute_units=8,
    )


def test_execution_start_rejects_second_active_session_for_same_task(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-duplicate-active-execution-authority"
    runtime.tasks.add_task(task_id, title="single active execution authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)
    runtime.execution.bind_backend(
        identity.agent_id,
        DeterministicFixtureBackend(
            actions=(ExecutionAction.complete(reason="eventual completion"),),
            backend_id="duplicate-active-execution-backend-v1",
            checkpoint_digest="duplicate-active-execution-checkpoint-v1",
        ),
    )

    first_workspace = _workspace(tmp_path / "first")
    second_workspace = _workspace(tmp_path / "second")
    first = runtime.execution.start(
        agent_id=identity.agent_id,
        task_id=task_id,
        workspace=first_workspace,
        action_schema=("filesystem.read_text",),
        budget=_budget(),
    )
    first_before = runtime.execution.get_session(first.session_id)

    try:
        with pytest.raises(ValueError, match="active execution|execution.*already active"):
            runtime.execution.start(
                agent_id=identity.agent_id,
                task_id=task_id,
                workspace=second_workspace,
                action_schema=("filesystem.read_text",),
                budget=_budget(),
            )

        assert runtime.execution.get_session(first.session_id) == first_before
        assert second_workspace.active_execution_epoch_id is None
        assert second_workspace.active_execution_epoch_owner is None
        active = [
            row
            for row in runtime.execution.to_state()["sessions"]
            if row["task_id"] == task_id and row["terminal_receipt_id"] is None
        ]
        assert len(active) == 1
        assert active[0]["session_id"] == first.session_id
    finally:
        first_workspace.close()
        second_workspace.close()
