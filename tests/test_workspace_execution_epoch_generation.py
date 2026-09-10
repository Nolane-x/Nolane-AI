from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

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
    _git(source, "config", "user.email", "workspace-epoch-generation@example.invalid")
    _git(source, "config", "user.name", "Workspace Epoch Generation")
    (source / "README.md").write_text("workspace epoch generation base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def test_workspace_execution_epoch_generation_tracks_claim_generations_not_epoch_ids(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    owner = "session-workspace-generation"
    try:
        assert workspace.execution_epoch_generation == 0

        epoch_id = workspace.claim_execution_epoch(owner)
        assert workspace.execution_epoch_generation == 1

        # Reasserting an already-active epoch for the same owner is idempotent.
        assert workspace.claim_execution_epoch(owner) == epoch_id
        assert workspace.execution_epoch_generation == 1

        workspace.release_execution_epoch(owner, epoch_id)
        assert workspace.execution_epoch_generation == 1

        # Reusing the persisted epoch id still creates a fresh authority generation.
        assert workspace.claim_execution_epoch(owner, expected_epoch_id=epoch_id) == epoch_id
        assert workspace.execution_epoch_generation == 2
    finally:
        workspace.close()


def test_workspace_execution_epoch_generation_is_not_advanced_by_failed_release(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    owner = "session-workspace-generation-owner"
    try:
        epoch_id = workspace.claim_execution_epoch(owner)
        generation = workspace.execution_epoch_generation

        with pytest.raises(PermissionError):
            workspace.release_execution_epoch("different-session", epoch_id)

        assert workspace.execution_epoch_generation == generation
        assert workspace.active_execution_epoch_id == epoch_id
        assert workspace.active_execution_epoch_owner == owner
    finally:
        workspace.close()
