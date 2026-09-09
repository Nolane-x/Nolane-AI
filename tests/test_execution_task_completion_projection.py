from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.execution import ExecutionTerminalReceipt
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionBudget,
    InferenceRequest,
)
from nolane.external_core.execution_workspace import RepositoryWorkspace
from nolane.neural.inference_bridge import DeterministicFixtureBackend


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
    _git(source, "config", "user.email", "task-projection@example.invalid")
    _git(source, "config", "user.name", "Task Projection")
    (source / "README.md").write_text("task projection base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def test_restore_rejects_task_completion_projection_not_bound_to_execution_terminal(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-execution-task-result-projection"
    runtime.tasks.add_task(task_id, title="task result projection", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    claimed = runtime.artifacts.put(
        kind="task-projection-authoritative-output",
        producer_agent_id=identity.agent_id,
        content="authoritative execution output\n",
        metadata={"task_id": task_id},
    )
    unrelated = runtime.artifacts.put(
        kind="task-projection-unrelated-same-task-output",
        producer_agent_id=identity.agent_id,
        content="canonical but not produced by this execution\n",
        metadata={"task_id": task_id},
    )
    backend = DeterministicFixtureBackend(
        actions=(
            ExecutionAction.complete(
                reason="complete with authoritative output",
                output_artifact_ids=(claimed.artifact_id,),
            ),
        ),
        backend_id="task-projection-backend-v1",
        checkpoint_digest="task-projection-checkpoint-v1",
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

    try:
        terminal = runtime.execution.step(session.session_id)
        assert isinstance(terminal, ExecutionTerminalReceipt)
        assert terminal.state.value == "completed"
        task = runtime.tasks.get(task_id)
        assert task.completed_by == identity.agent_id
        assert task.output_artifact_ids == terminal.output_artifact_ids
        assert unrelated.artifact_id not in terminal.output_artifact_ids

        state = runtime.to_state()
        task_rows = state["tasks"]["tasks"]
        poisoned_rows = []
        for row in task_rows:
            if row["task_id"] == task_id:
                poisoned = dict(row)
                poisoned["output_artifact_ids"] = [unrelated.artifact_id]
                poisoned_rows.append(poisoned)
            else:
                poisoned_rows.append(row)
        state["tasks"]["tasks"] = poisoned_rows

        with pytest.raises(
            ValueError,
            match="task.*(completion|output).*(binding|projection)|result.*projection",
        ):
            OrganizationRuntime.from_state(state)
    finally:
        workspace.close()


def test_live_task_completion_projection_cannot_be_rebound_after_completion() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-live-completion-projection-rebind"
    runtime.tasks.add_task(task_id, title="live completion projection", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    authoritative = runtime.artifacts.put(
        kind="task-live-authoritative-output",
        producer_agent_id=identity.agent_id,
        content="first authoritative task completion\n",
        metadata={"task_id": task_id},
    )
    replacement = runtime.artifacts.put(
        kind="task-live-replacement-output",
        producer_agent_id=identity.agent_id,
        content="later same-agent output must not replace terminal task projection\n",
        metadata={"task_id": task_id},
    )

    completed = runtime.tasks.complete(
        task_id,
        identity.agent_id,
        output_artifact_ids=(authoritative.artifact_id,),
    )
    assert completed.completed_by == identity.agent_id
    assert completed.output_artifact_ids == (authoritative.artifact_id,)

    with pytest.raises(ValueError, match="already completed"):
        runtime.tasks.complete(
            task_id,
            identity.agent_id,
            output_artifact_ids=(replacement.artifact_id,),
        )

    assert runtime.tasks.get(task_id) == completed


def test_execution_start_rejects_already_completed_task_before_workspace_epoch(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-start-completed-authority"
    runtime.tasks.add_task(task_id, title="completed start authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    output = runtime.artifacts.put(
        kind="task-start-completed-output",
        producer_agent_id=identity.agent_id,
        content="already completed before execution start\n",
        metadata={"task_id": task_id},
    )
    runtime.tasks.complete(
        task_id,
        identity.agent_id,
        output_artifact_ids=(output.artifact_id,),
    )
    backend = DeterministicFixtureBackend(
        actions=(
            ExecutionAction.complete(
                reason="must never run",
                output_artifact_ids=(output.artifact_id,),
            ),
        ),
        backend_id="task-start-completed-backend-v1",
        checkpoint_digest="task-start-completed-checkpoint-v1",
    )
    runtime.execution.bind_backend(identity.agent_id, backend)
    workspace = _workspace(tmp_path)

    try:
        with pytest.raises(ValueError, match="task.*completed|completed.*task"):
            runtime.execution.start(
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
        assert runtime.execution.sessions() == ()
        assert workspace.active_execution_epoch_id is None
        assert workspace.active_execution_epoch_owner is None
    finally:
        workspace.close()


def test_live_execution_rejects_task_completed_outside_terminal_authority(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-live-completion-authority-conflict"
    runtime.tasks.add_task(task_id, title="live completion authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    claimed = runtime.artifacts.put(
        kind="task-live-execution-output",
        producer_agent_id=identity.agent_id,
        content="execution-owned output\n",
        metadata={"task_id": task_id},
    )
    conflicting = runtime.artifacts.put(
        kind="task-live-external-completion-output",
        producer_agent_id=identity.agent_id,
        content="same task but outside terminal authority\n",
        metadata={"task_id": task_id},
    )
    backend = DeterministicFixtureBackend(
        actions=(
            ExecutionAction.complete(
                reason="execution attempts canonical completion",
                output_artifact_ids=(claimed.artifact_id,),
            ),
        ),
        backend_id="task-live-conflict-backend-v1",
        checkpoint_digest="task-live-conflict-checkpoint-v1",
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

    try:
        runtime.tasks.complete(
            task_id,
            identity.agent_id,
            output_artifact_ids=(conflicting.artifact_id,),
        )
        session_before = runtime.execution.get_session(session.session_id)
        task_before = runtime.tasks.get(task_id)

        with pytest.raises(
            ValueError,
            match="task.*completion.*authority|completion.*task.*authority",
        ):
            runtime.execution.step(session.session_id)

        assert runtime.execution.get_session(session.session_id) == session_before
        assert runtime.tasks.get(task_id) == task_before
        assert runtime.execution.get_session(session.session_id).terminal_receipt_id is None
        assert runtime.execution.get_session(session.session_id).decision_receipt_ids == ()
    finally:
        workspace.close()


def test_completion_authority_revalidated_after_backend_decision_before_mutation(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-mid-decision-completion-race"
    runtime.tasks.add_task(task_id, title="mid-decision completion race", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    claimed = runtime.artifacts.put(
        kind="mid-decision-execution-output",
        producer_agent_id=identity.agent_id,
        content="execution output that must not win after authority changes\n",
        metadata={"task_id": task_id},
    )
    conflicting = runtime.artifacts.put(
        kind="mid-decision-conflicting-output",
        producer_agent_id=identity.agent_id,
        content="completion authority claimed while backend is deciding\n",
        metadata={"task_id": task_id},
    )

    class _CompletionStealingBackend:
        backend_id = "mid-decision-completion-race-backend-v1"
        checkpoint_digest = "mid-decision-completion-race-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            runtime.tasks.complete(
                task_id,
                identity.agent_id,
                output_artifact_ids=(conflicting.artifact_id,),
            )
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion decision must be rejected",
                    output_artifact_ids=(claimed.artifact_id,),
                ),
            )

    backend = _CompletionStealingBackend()
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

    try:
        session_before = runtime.execution.get_session(session.session_id)
        with pytest.raises(
            ValueError,
            match="completion.*authority|task.*completed|completed.*task",
        ):
            runtime.execution.step(session.session_id)

        task = runtime.tasks.get(task_id)
        assert task.completed_by == identity.agent_id
        assert task.output_artifact_ids == (conflicting.artifact_id,)
        assert runtime.execution.get_session(session.session_id) == session_before
        assert runtime.execution.get_session(session.session_id).decision_receipt_ids == ()
        assert runtime.execution.get_session(session.session_id).terminal_receipt_id is None
        assert runtime.execution.terminal_receipts() == ()
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id
    finally:
        workspace.close()
