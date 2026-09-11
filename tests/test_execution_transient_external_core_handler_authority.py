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
    _git(source, "config", "user.email", "handler-authority@example.invalid")
    _git(source, "config", "user.name", "Handler Authority")
    (source / "README.md").write_text("handler authority base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def test_tool_step_rejects_handler_first_registered_during_inference_before_dispatch(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.get("requirements.chief")
    tool_id = "requirements-graph"
    operation = "inspect"
    assert tool_id in identity.external_core_bindings
    assert runtime.external_cores.get(tool_id).core_id == tool_id

    task_id = "task-transient-external-core-handler-authority"
    runtime.tasks.add_task(task_id, title="transient handler authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    handler_calls: list[dict[str, object]] = []

    def handler(_workspace: RepositoryWorkspace, arguments: dict[str, object]):
        handler_calls.append(dict(arguments))
        return {"observed": str(arguments.get("query", ""))}

    class _RegisteringToolBackend:
        def __init__(self) -> None:
            self.backend_id = "transient-handler-authority-backend-v1"
            self.checkpoint_digest = "transient-handler-authority-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            assert f"{tool_id}.{operation}" in request.action_schema
            runtime.execution.executor.register_handler(tool_id, handler)
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.tool(
                    ToolAction.from_arguments(
                        tool_id,
                        operation,
                        {"query": "authority snapshot"},
                    )
                ),
            )

    backend = _RegisteringToolBackend()
    runtime.execution.bind_backend(identity.agent_id, backend)
    workspace = _workspace(tmp_path)
    session = runtime.execution.start(
        agent_id=identity.agent_id,
        task_id=task_id,
        workspace=workspace,
        action_schema=(f"{tool_id}.{operation}",),
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
        executor_receipts_before = runtime.execution.executor.receipts()
        workspace_digest_before = workspace.digest

        with pytest.raises(
            PermissionError,
            match="handler.*binding|external.*core.*handler|handler.*authority|core.*binding",
        ):
            runtime.execution.step(session.session_id)

        # The external registration itself remains available for a fresh retry,
        # but the stale decision must not dispatch it or persist execution state.
        assert handler_calls == []
        assert runtime.execution.executor.receipts() == executor_receipts_before

        task = runtime.tasks.get(task_id)
        assert task.completed_by is None
        assert task.aborted_by is None
        assert task.leased_to == identity.agent_id

        assert runtime.execution.get_session(session.session_id) == session_before
        assert runtime.execution.to_state() == execution_before
        assert runtime.execution.get_session(session.session_id).decision_receipt_ids == ()
        assert runtime.execution.get_session(session.session_id).step_receipt_ids == ()
        assert runtime.execution.get_session(session.session_id).core_receipt_ids == ()
        assert runtime.execution.get_session(session.session_id).terminal_receipt_id is None
        assert runtime.execution.terminal_receipts() == ()

        assert workspace.digest == workspace_digest_before
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id
    finally:
        workspace.close()
