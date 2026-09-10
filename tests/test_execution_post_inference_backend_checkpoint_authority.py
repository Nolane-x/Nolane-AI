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
    _git(source, "config", "user.email", "backend-checkpoint-authority@example.invalid")
    _git(source, "config", "user.name", "Backend Checkpoint Authority")
    (source / "README.md").write_text("backend checkpoint authority base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def test_completion_revalidates_live_backend_checkpoint_after_inference_before_persisting_decision(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-post-inference-backend-checkpoint-authority"
    runtime.tasks.add_task(task_id, title="backend checkpoint authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    class _CheckpointChangingCompletionBackend:
        def __init__(self) -> None:
            self.backend_id = "post-inference-backend-checkpoint-v1"
            self.checkpoint_digest = "post-inference-checkpoint-v1"
            self.initial_checkpoint_digest = self.checkpoint_digest
            self.replacement_checkpoint_digest = "post-inference-checkpoint-v2"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            assert request.checkpoint_digest == self.initial_checkpoint_digest
            self.checkpoint_digest = self.replacement_checkpoint_digest
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after live backend checkpoint changed during inference",
                ),
            )

    backend = _CheckpointChangingCompletionBackend()
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
        execution_before = runtime.execution.to_state()
        workspace_digest_before = workspace.digest
        assert session.checkpoint_digest == backend.initial_checkpoint_digest

        with pytest.raises(
            RuntimeError,
            match="backend.*checkpoint|checkpoint.*backend|execution.*authority",
        ):
            runtime.execution.step(session.session_id)

        assert backend.checkpoint_digest == backend.replacement_checkpoint_digest

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


def test_completion_revalidates_live_backend_identity_after_inference_before_persisting_decision(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-post-inference-backend-identity-authority"
    runtime.tasks.add_task(task_id, title="backend identity authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    class _IdentityChangingCompletionBackend:
        def __init__(self) -> None:
            self.backend_id = "post-inference-backend-identity-v1"
            self.initial_backend_id = self.backend_id
            self.replacement_backend_id = "post-inference-backend-identity-v2"
            self.checkpoint_digest = "post-inference-backend-identity-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            assert request.checkpoint_digest == self.checkpoint_digest
            self.backend_id = self.replacement_backend_id
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after live backend identity changed during inference",
                ),
            )

    backend = _IdentityChangingCompletionBackend()
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
        execution_before = runtime.execution.to_state()
        workspace_digest_before = workspace.digest
        assert session.backend_id == backend.initial_backend_id

        with pytest.raises(
            RuntimeError,
            match="backend.*identity|backend.*id|execution.*authority",
        ):
            runtime.execution.step(session.session_id)

        assert backend.backend_id == backend.replacement_backend_id

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


def test_completion_rejects_transient_backend_rebind_to_distinct_equivalent_backend(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-post-inference-transient-backend-binding-authority"
    runtime.tasks.add_task(task_id, title="transient backend binding authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    backend_id = "post-inference-backend-binding-v1"
    checkpoint_digest = "post-inference-backend-binding-checkpoint-v1"

    class _EquivalentReplacementBackend:
        def __init__(self) -> None:
            self.backend_id = backend_id
            self.checkpoint_digest = checkpoint_digest

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            raise AssertionError("replacement backend must not execute the stale request")

    replacement_backend = _EquivalentReplacementBackend()

    class _RebindingCompletionBackend:
        def __init__(self) -> None:
            self.backend_id = backend_id
            self.checkpoint_digest = checkpoint_digest

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            assert request.checkpoint_digest == self.checkpoint_digest
            runtime.execution.bind_backend(identity.agent_id, replacement_backend)
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after backend binding authority changed during inference",
                ),
            )

    original_backend = _RebindingCompletionBackend()
    runtime.execution.bind_backend(identity.agent_id, original_backend)
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
        assert session.backend_id == backend_id
        assert session.checkpoint_digest == checkpoint_digest

        with pytest.raises(
            PermissionError,
            match="backend.*binding|backend.*authority|inference.*backend|rebound.*inference",
        ):
            runtime.execution.step(session.session_id)

        # The canonical external rebind remains visible for retry/recovery, while
        # the stale decision itself must leave no persisted execution effects.
        assert runtime.execution._backends[identity.agent_id] is replacement_backend

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
