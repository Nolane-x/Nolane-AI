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
    _git(source, "config", "user.email", "post-inference-neural-version@example.invalid")
    _git(source, "config", "user.name", "Post Inference Neural Version")
    (source / "README.md").write_text("neural version authority base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def test_completion_revalidates_neural_version_authority_after_inference_before_persisting_decision(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    initial_neural_version = identity.neural_version
    replacement_neural_version = initial_neural_version + ".post-inference"
    task_id = "task-post-inference-neural-version-authority"
    runtime.tasks.add_task(task_id, title="neural version authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    workspace = _workspace(tmp_path)

    class _NeuralVersionChangingCompletionBackend:
        backend_id = "post-inference-neural-version-backend-v1"
        checkpoint_digest = "post-inference-neural-version-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            assert request.neural_version == initial_neural_version
            runtime.registry.accept_neural_version(
                identity.agent_id,
                replacement_neural_version,
            )
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after neural version changed during inference",
                ),
            )

    runtime.execution.bind_backend(
        identity.agent_id,
        _NeuralVersionChangingCompletionBackend(),
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
            ValueError,
            match="neural.*version|version.*neural|identity.*authority|execution.*authority",
        ):
            runtime.execution.step(session.session_id)

        current_identity = runtime.registry.get(identity.agent_id)
        assert current_identity.neural_version == replacement_neural_version
        assert replacement_neural_version in runtime.registry.accepted_versions(identity.agent_id)

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


def test_completion_rejects_transient_neural_version_switch_even_after_original_version_is_restored(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    initial_neural_version = identity.neural_version
    alternate_neural_version = initial_neural_version + ".previously-accepted"

    # Make the alternate version part of accepted history before the execution
    # starts, then restore the original. This prevents accepted-version history
    # growth from accidentally acting as the transient-mutation detector.
    runtime.registry.accept_neural_version(identity.agent_id, alternate_neural_version)
    runtime.registry.accept_neural_version(identity.agent_id, initial_neural_version)
    accepted_versions_before = runtime.registry.accepted_versions(identity.agent_id)
    assert alternate_neural_version in accepted_versions_before
    assert runtime.registry.get(identity.agent_id).neural_version == initial_neural_version

    task_id = "task-post-inference-transient-neural-version-authority"
    runtime.tasks.add_task(task_id, title="transient neural version authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)
    workspace = _workspace(tmp_path)

    class _TransientNeuralVersionCompletionBackend:
        backend_id = "post-inference-transient-neural-version-backend-v1"
        checkpoint_digest = "post-inference-transient-neural-version-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            assert request.neural_version == initial_neural_version
            runtime.registry.accept_neural_version(identity.agent_id, alternate_neural_version)
            assert runtime.registry.get(identity.agent_id).neural_version == alternate_neural_version
            runtime.registry.accept_neural_version(identity.agent_id, initial_neural_version)
            assert runtime.registry.get(identity.agent_id).neural_version == initial_neural_version
            assert runtime.registry.accepted_versions(identity.agent_id) == accepted_versions_before
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after transient neural version authority switch",
                ),
            )

    runtime.execution.bind_backend(
        identity.agent_id,
        _TransientNeuralVersionCompletionBackend(),
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
            PermissionError,
            match="neural.*version|version.*authority|execution.*authority|revoked.*inference",
        ):
            runtime.execution.step(session.session_id)

        assert runtime.registry.get(identity.agent_id).neural_version == initial_neural_version
        assert runtime.registry.accepted_versions(identity.agent_id) == accepted_versions_before

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
