from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.execution import ExecutionStepReceipt
from nolane.external_core.execution_types import (
    DeterministicFixtureBackend,
    ExecutionAction,
    ExecutionBudget,
    ToolAction,
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
    _git(source, "config", "user.email", "result-projection@example.invalid")
    _git(source, "config", "user.name", "Result Projection")
    (source / "README.md").write_text("result projection base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def _runtime_with_tool_step(tmp_path: Path):
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-execution-result-projection"
    runtime.tasks.add_task(task_id, title="execution result projection", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)
    backend = DeterministicFixtureBackend(
        actions=(
            ExecutionAction.tool(
                ToolAction.from_arguments(
                    "filesystem",
                    "read_text",
                    {"path": "README.md"},
                )
            ),
        ),
        backend_id="result-projection-backend-v1",
        checkpoint_digest="result-projection-checkpoint-v1",
    )
    runtime.execution.bind_backend(identity.agent_id, backend)
    workspace = _workspace(tmp_path)
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
    step = runtime.execution.step(session.session_id)
    assert isinstance(step, ExecutionStepReceipt)
    assert step.core_receipt_id is not None
    core = runtime.execution.executor.get_receipt(step.core_receipt_id)
    assert tuple(core.output_artifact_ids) == step.output_artifact_ids
    assert step.output_artifact_ids
    unrelated = runtime.artifacts.put(
        kind="result-projection-unrelated",
        producer_agent_id=identity.agent_id,
        content="unrelated artifact\n",
        metadata={"task_id": task_id},
    )
    assert unrelated.artifact_id not in step.output_artifact_ids
    return runtime, session, step, core, unrelated, workspace


def _execution_session_state(execution_state: dict, session_id: str) -> dict:
    rows = [row for row in execution_state["sessions"] if row["session_id"] == session_id]
    assert len(rows) == 1
    return dict(rows[0])


def test_restore_rejects_canonical_step_output_projection_that_disagrees_with_core_receipt(
    tmp_path: Path,
) -> None:
    runtime, session, step, _core, unrelated, workspace = _runtime_with_tool_step(tmp_path)
    try:
        state = runtime.to_state()
        execution_state = state["execution"]
        session_state = _execution_session_state(execution_state, session.session_id)

        poisoned_step = ExecutionStepReceipt.create(
            session_id=step.session_id,
            step_index=step.step_index,
            decision_receipt_id=step.decision_receipt_id,
            core_receipt_id=step.core_receipt_id,
            before_workspace_digest=step.before_workspace_digest,
            after_workspace_digest=step.after_workspace_digest,
            state_after=step.state_after,
            output_artifact_ids=(unrelated.artifact_id,),
            core_contract_digest=step.core_contract_digest,
            workspace_epoch_id=step.workspace_epoch_id,
        )
        session_state["step_receipt_ids"] = [poisoned_step.receipt_id]
        session_state["output_artifact_ids"] = [unrelated.artifact_id]
        execution_state["sessions"] = [session_state]
        execution_state["steps"] = [poisoned_step.to_state()]

        with pytest.raises(ValueError, match="output.*(binding|projection)|result.*projection"):
            OrganizationRuntime.from_state(state)
    finally:
        workspace.close()


def test_restore_rejects_canonical_session_output_projection_not_grounded_in_step_results(
    tmp_path: Path,
) -> None:
    runtime, session, step, _core, unrelated, workspace = _runtime_with_tool_step(tmp_path)
    try:
        state = runtime.to_state()
        execution_state = state["execution"]
        session_state = _execution_session_state(execution_state, session.session_id)
        assert session_state["output_artifact_ids"] == list(step.output_artifact_ids)

        session_state["output_artifact_ids"] = [unrelated.artifact_id]
        execution_state["sessions"] = [session_state]

        with pytest.raises(ValueError, match="output.*(binding|projection)|result.*projection"):
            OrganizationRuntime.from_state(state)
    finally:
        workspace.close()
