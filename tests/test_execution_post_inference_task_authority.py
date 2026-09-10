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
    _git(source, "config", "user.email", "post-inference-authority@example.invalid")
    _git(source, "config", "user.name", "Post Inference Authority")
    (source / "README.md").write_text("post inference authority base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def test_tool_action_revalidates_task_completion_authority_after_inference_before_dispatch(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-post-inference-stale-tool-authority"
    runtime.tasks.add_task(task_id, title="stale tool authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    authoritative = runtime.artifacts.put(
        kind="post-inference-authoritative-completion",
        producer_agent_id=identity.agent_id,
        content="completion claimed while inference is running\n",
        metadata={"task_id": task_id},
    )

    class _CompletionStealingToolBackend:
        backend_id = "post-inference-stale-tool-backend-v1"
        checkpoint_digest = "post-inference-stale-tool-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            runtime.tasks.complete(
                task_id,
                identity.agent_id,
                output_artifact_ids=(authoritative.artifact_id,),
            )
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.tool(
                    ToolAction.from_arguments(
                        "filesystem",
                        "read_text",
                        {"path": "README.md"},
                    )
                ),
            )

    runtime.execution.bind_backend(identity.agent_id, _CompletionStealingToolBackend())
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
        execution_before = runtime.execution.to_state()
        workspace_digest_before = workspace.digest

        with pytest.raises(
            ValueError,
            match="task.*completion.*authority|completion.*task.*authority|task.*completed",
        ):
            runtime.execution.step(session.session_id)

        task = runtime.tasks.get(task_id)
        assert task.completed_by == identity.agent_id
        assert task.output_artifact_ids == (authoritative.artifact_id,)

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


def test_tool_action_revalidates_task_lease_authority_after_inference_before_dispatch(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-post-inference-stale-tool-lease"
    runtime.tasks.add_task(task_id, title="stale tool lease", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    class _LeaseReleasingToolBackend:
        backend_id = "post-inference-stale-tool-lease-backend-v1"
        checkpoint_digest = "post-inference-stale-tool-lease-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            runtime.tasks.release_lease(task_id, identity.agent_id)
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.tool(
                    ToolAction.from_arguments(
                        "filesystem",
                        "read_text",
                        {"path": "README.md"},
                    )
                ),
            )

    runtime.execution.bind_backend(identity.agent_id, _LeaseReleasingToolBackend())
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
        execution_before = runtime.execution.to_state()
        workspace_digest_before = workspace.digest

        with pytest.raises(
            (PermissionError, ValueError),
            match="task.*lease|lease.*task|execution.*authority",
        ):
            runtime.execution.step(session.session_id)

        task = runtime.tasks.get(task_id)
        assert task.leased_to is None
        assert task.completed_by is None
        assert task.aborted_by is None

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


def test_completion_revalidates_workspace_frontier_after_inference_before_persisting_decision(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-post-inference-workspace-frontier"
    runtime.tasks.add_task(task_id, title="workspace frontier authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    workspace = _workspace(tmp_path)

    class _WorkspaceMutatingCompletionBackend:
        backend_id = "post-inference-workspace-frontier-backend-v1"
        checkpoint_digest = "post-inference-workspace-frontier-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            workspace.write_text(
                "README.md",
                "mutated outside execution authority during inference\n",
            )
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after workspace frontier changed",
                ),
            )

    runtime.execution.bind_backend(
        identity.agent_id,
        _WorkspaceMutatingCompletionBackend(),
    )
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
            RuntimeError,
            match="workspace.*digest|workspace.*frontier|execution.*authority",
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

        assert workspace.digest != workspace_digest_before
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id
    finally:
        workspace.close()


def test_completion_revalidates_live_workspace_epoch_after_inference_before_persisting_decision(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-post-inference-live-workspace-epoch"
    runtime.tasks.add_task(task_id, title="live workspace epoch authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    workspace = _workspace(tmp_path)

    class _EpochReleasingCompletionBackend:
        backend_id = "post-inference-live-workspace-epoch-backend-v1"
        checkpoint_digest = "post-inference-live-workspace-epoch-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            assert request.execution_session_id is not None
            assert request.workspace_epoch_id is not None
            workspace.release_execution_epoch(
                request.execution_session_id,
                request.workspace_epoch_id,
            )
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after live workspace epoch was released",
                ),
            )

    runtime.execution.bind_backend(
        identity.agent_id,
        _EpochReleasingCompletionBackend(),
    )
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
            (RuntimeError, PermissionError),
            match="workspace.*epoch|execution.*authority",
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
        assert workspace.active_execution_epoch_id is None
        assert workspace.active_execution_epoch_owner is None
    finally:
        workspace.close()


def test_completion_revalidates_identity_pause_authority_after_inference_before_persisting_decision(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-post-inference-identity-pause-authority"
    runtime.tasks.add_task(task_id, title="identity pause authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    workspace = _workspace(tmp_path)

    class _PausingCompletionBackend:
        backend_id = "post-inference-identity-pause-backend-v1"
        checkpoint_digest = "post-inference-identity-pause-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            runtime.registry.set_status(identity.agent_id, AgentStatus.PAUSED)
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after identity was paused during inference",
                ),
            )

    runtime.execution.bind_backend(identity.agent_id, _PausingCompletionBackend())
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
            match="agent.*pause|pause.*agent|identity.*authority|execution.*authority",
        ):
            runtime.execution.step(session.session_id)

        task = runtime.tasks.get(task_id)
        assert task.completed_by is None
        assert task.aborted_by is None
        assert task.leased_to == identity.agent_id
        assert runtime.registry.get(identity.agent_id).status is AgentStatus.PAUSED

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
