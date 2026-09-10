from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.execution_types import ExecutionBudget
from nolane.external_core.execution_workspace import RepositoryWorkspace


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _source_repo(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "workspace-attachment-revision@example.invalid")
    _git(source, "config", "user.name", "Workspace Attachment Revision")
    (source / "README.md").write_text("workspace attachment revision base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return source


def _workspace(source: Path, target: Path) -> RepositoryWorkspace:
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=target,
    )


def _start_session(runtime: OrganizationRuntime, workspace: RepositoryWorkspace):
    identity = runtime.registry.identities()[0]
    task_id = "task-workspace-attachment-authority-revision"
    runtime.tasks.add_task(task_id, title="workspace attachment authority revision", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    class _Backend:
        backend_id = "workspace-attachment-authority-revision-backend-v1"
        checkpoint_digest = "workspace-attachment-authority-revision-checkpoint-v1"

        def decide(self, request):  # pragma: no cover - this contract never executes inference
            raise AssertionError("revision contract must not execute inference")

    runtime.execution.bind_backend(identity.agent_id, _Backend())
    return runtime.execution.start(
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


def test_workspace_attachment_authority_revision_tracks_successful_mapping_generations(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    source = _source_repo(tmp_path)
    original = _workspace(source, tmp_path / "workspace-original")
    replacement = _workspace(source, tmp_path / "workspace-replacement")

    try:
        session = _start_session(runtime, original)
        assert runtime.execution.workspace_attachment_authority_revision(session.session_id) == 1

        # Reasserting the exact live workspace does not change attachment authority.
        runtime.execution.attach_workspace(session.session_id, original)
        assert runtime.execution.workspace_attachment_authority_revision(session.session_id) == 1

        # A distinct but proof-equivalent workspace is a new live attachment generation.
        assert replacement is not original
        assert replacement.root != original.root
        assert replacement.digest == original.digest
        runtime.execution.attach_workspace(session.session_id, replacement)
        assert runtime.execution.workspace_attachment_authority_revision(session.session_id) == 2
    finally:
        original.close()
        replacement.close()


def test_workspace_attachment_authority_revision_is_not_advanced_by_failed_attach(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    source = _source_repo(tmp_path)
    original = _workspace(source, tmp_path / "workspace-original")
    invalid = _workspace(source, tmp_path / "workspace-invalid")

    try:
        session = _start_session(runtime, original)
        revision = runtime.execution.workspace_attachment_authority_revision(session.session_id)
        invalid.write_text("uncommitted.txt", "different workspace digest\n")
        assert invalid.digest != original.digest

        with pytest.raises((ValueError, PermissionError, RuntimeError)):
            runtime.execution.attach_workspace(session.session_id, invalid)

        assert runtime.execution.workspace_attachment_authority_revision(session.session_id) == revision
    finally:
        original.close()
        invalid.close()
