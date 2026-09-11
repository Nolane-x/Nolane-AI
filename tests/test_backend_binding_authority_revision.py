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


class _Backend:
    def __init__(self, *, backend_id: str, checkpoint_digest: str) -> None:
        self.backend_id = backend_id
        self.checkpoint_digest = checkpoint_digest

    def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
        raise AssertionError("backend binding revision contract does not execute inference")


def test_backend_binding_authority_revision_tracks_distinct_successful_bindings() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    backend_a = _Backend(
        backend_id="backend-binding-revision-v1",
        checkpoint_digest="backend-binding-revision-checkpoint-v1",
    )
    backend_b = _Backend(
        backend_id=backend_a.backend_id,
        checkpoint_digest=backend_a.checkpoint_digest,
    )

    assert runtime.execution.backend_binding_authority_revision(identity.agent_id) == 0

    runtime.execution.bind_backend(identity.agent_id, backend_a)
    assert runtime.execution.backend_binding_authority_revision(identity.agent_id) == 1

    # Reasserting the exact same backend object is idempotent authority.
    runtime.execution.bind_backend(identity.agent_id, backend_a)
    assert runtime.execution.backend_binding_authority_revision(identity.agent_id) == 1

    # A proof-equivalent but distinct backend is a fresh binding generation.
    runtime.execution.bind_backend(identity.agent_id, backend_b)
    assert runtime.execution.backend_binding_authority_revision(identity.agent_id) == 2


def test_backend_binding_authority_revision_is_not_advanced_by_failed_bind() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    backend = _Backend(
        backend_id="backend-binding-failed-bind-v1",
        checkpoint_digest="backend-binding-failed-bind-checkpoint-v1",
    )
    runtime.execution.bind_backend(identity.agent_id, backend)
    revision = runtime.execution.backend_binding_authority_revision(identity.agent_id)

    invalid = _Backend(
        backend_id="",
        checkpoint_digest=backend.checkpoint_digest,
    )
    with pytest.raises(ValueError):
        runtime.execution.bind_backend(identity.agent_id, invalid)

    assert runtime.execution.backend_binding_authority_revision(identity.agent_id) == revision
    assert runtime.execution._backends[identity.agent_id] is backend


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _execution_frontier_workspace(tmp_path: Path) -> RepositoryWorkspace:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "execution-frontier@example.invalid")
    _git(source, "config", "user.name", "Execution Frontier Authority")
    (source / "README.md").write_text("same-session frontier base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def test_same_session_reentrant_step_rejects_stale_outer_frontier_before_persistence(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-same-session-execution-frontier"
    runtime.tasks.add_task(task_id, title="same-session execution frontier", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    class _ReentrantBackend:
        backend_id = "same-session-execution-frontier-backend-v1"
        checkpoint_digest = "same-session-execution-frontier-checkpoint-v1"

        def __init__(self) -> None:
            self.session_id = ""
            self.depth = 0
            self.inner_state: dict[str, object] | None = None
            self.inner_session = None

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            if self.depth == 0:
                assert self.session_id
                self.depth = 1
                try:
                    runtime.execution.step(self.session_id)
                    self.inner_session = runtime.execution.get_session(self.session_id)
                    self.inner_state = runtime.execution.to_state()
                finally:
                    self.depth = 0
                return AgentDecisionReceipt.create(
                    backend_id=self.backend_id,
                    request=request,
                    action=ExecutionAction.wait(reason="stale outer frontier"),
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

    backend = _ReentrantBackend()
    runtime.execution.bind_backend(identity.agent_id, backend)
    workspace = _execution_frontier_workspace(tmp_path)
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
    backend.session_id = session.session_id

    try:
        workspace_digest_before = workspace.digest

        with pytest.raises(
            PermissionError,
            match="execution.*frontier|session.*frontier|frontier.*authority",
        ):
            runtime.execution.step(session.session_id)

        assert backend.inner_session is not None
        assert backend.inner_state is not None
        current = runtime.execution.get_session(session.session_id)
        assert current == backend.inner_session
        assert runtime.execution.to_state() == backend.inner_state
        assert current.step_index == 1
        assert current.counters.steps == 1
        assert current.counters.tool_calls == 1
        assert len(current.decision_receipt_ids) == 1
        assert len(current.step_receipt_ids) == 1
        assert current.terminal_receipt_id is None

        task = runtime.tasks.get(task_id)
        assert task.leased_to == identity.agent_id
        assert task.completed_by is None
        assert task.aborted_by is None
        assert workspace.digest == workspace_digest_before
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id
    finally:
        workspace.close()


def test_self_model_change_during_inference_rejects_decision_before_persistence(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    original_version = identity.self_model_version
    changed_version = original_version + "-during-inference"
    task_id = "task-same-request-self-model-direct"
    runtime.tasks.add_task(task_id, title="same-request self-model direct", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    class _SelfModelMutatingBackend:
        backend_id = "same-request-self-model-direct-backend-v1"
        checkpoint_digest = "same-request-self-model-direct-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            runtime.registry.set_self_model_version(identity.agent_id, changed_version)
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.wait(reason="stale self-model decision"),
            )

    runtime.execution.bind_backend(identity.agent_id, _SelfModelMutatingBackend())
    workspace = _execution_frontier_workspace(tmp_path)
    session = runtime.execution.start(
        agent_id=identity.agent_id,
        task_id=task_id,
        workspace=workspace,
        action_schema=("filesystem.read_text",),
        budget=ExecutionBudget(
            max_steps=4,
            max_tool_calls=4,
            max_external_core_calls=4,
            max_compute_units=4,
        ),
    )

    try:
        execution_state_before = runtime.execution.to_state()
        workspace_digest_before = workspace.digest

        with pytest.raises(
            PermissionError,
            match="self-model.*authority|authority.*self-model",
        ):
            runtime.execution.step(session.session_id)

        assert runtime.registry.get(identity.agent_id).self_model_version == changed_version
        assert runtime.execution.to_state() == execution_state_before
        current = runtime.execution.get_session(session.session_id)
        assert current.step_index == 0
        assert current.counters.steps == 0
        assert current.decision_receipt_ids == ()
        assert current.step_receipt_ids == ()
        assert current.terminal_receipt_id is None
        task = runtime.tasks.get(task_id)
        assert task.leased_to == identity.agent_id
        assert task.completed_by is None
        assert task.aborted_by is None
        assert workspace.digest == workspace_digest_before
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id
    finally:
        workspace.close()


def test_self_model_aba_change_during_inference_rejects_decision_before_persistence(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    original_version = identity.self_model_version
    transient_version = original_version + "-transient"
    task_id = "task-same-request-self-model-aba"
    runtime.tasks.add_task(task_id, title="same-request self-model aba", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    class _SelfModelABABackend:
        backend_id = "same-request-self-model-aba-backend-v1"
        checkpoint_digest = "same-request-self-model-aba-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            runtime.registry.set_self_model_version(identity.agent_id, transient_version)
            runtime.registry.set_self_model_version(identity.agent_id, original_version)
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.wait(reason="aba stale self-model decision"),
            )

    runtime.execution.bind_backend(identity.agent_id, _SelfModelABABackend())
    workspace = _execution_frontier_workspace(tmp_path)
    session = runtime.execution.start(
        agent_id=identity.agent_id,
        task_id=task_id,
        workspace=workspace,
        action_schema=("filesystem.read_text",),
        budget=ExecutionBudget(
            max_steps=4,
            max_tool_calls=4,
            max_external_core_calls=4,
            max_compute_units=4,
        ),
    )

    try:
        execution_state_before = runtime.execution.to_state()
        workspace_digest_before = workspace.digest

        with pytest.raises(
            PermissionError,
            match="self-model.*authority|authority.*self-model",
        ):
            runtime.execution.step(session.session_id)

        assert runtime.registry.get(identity.agent_id).self_model_version == original_version
        assert runtime.execution.to_state() == execution_state_before
        current = runtime.execution.get_session(session.session_id)
        assert current.step_index == 0
        assert current.counters.steps == 0
        assert current.decision_receipt_ids == ()
        assert current.step_receipt_ids == ()
        assert current.terminal_receipt_id is None
        task = runtime.tasks.get(task_id)
        assert task.leased_to == identity.agent_id
        assert task.completed_by is None
        assert task.aborted_by is None
        assert workspace.digest == workspace_digest_before
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id
    finally:
        workspace.close()
