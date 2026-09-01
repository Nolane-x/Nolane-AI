from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from nolane.external_core.execution_workspace import RepositoryWorkspace, WorkspaceCheckpoint


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "acting-tests@example.invalid")
    _git(repo, "config", "user.name", "Acting Tests")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return repo


def _claim(workspace: RepositoryWorkspace, owner: str = "execution-test") -> str:
    return workspace.claim_execution_epoch(owner)


def test_checkpoint_restores_tracked_and_untracked_workspace_state(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    workspace = RepositoryWorkspace.create(
        source_repo=repo,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )
    try:
        _claim(workspace)
        before = workspace.digest
        checkpoint = workspace.checkpoint(label="before-action")

        workspace.write_text("README.md", "mutated\n")
        workspace.write_text("generated/new.txt", "ephemeral\n")
        assert workspace.digest != before

        restored = workspace.restore(checkpoint)
        assert restored == before
        assert workspace.digest == before
        assert workspace.read_text("README.md") == "base\n"
        assert not workspace.resolve_repo_path("generated/new.txt").exists()

        workspace.release_checkpoint(checkpoint)
        assert not checkpoint.snapshot_root.exists()
    finally:
        workspace.close()


def test_ignored_payload_is_part_of_digest_and_rollback_proof(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    workspace = RepositoryWorkspace.create(source_repo=repo, revision="HEAD", workspace_root=tmp_path / "workspace")
    try:
        _claim(workspace)
        workspace.write_text(".gitignore", "ignored/\n")
        before = workspace.digest
        checkpoint = workspace.checkpoint(label="before-ignored-payload")

        workspace.write_text("ignored/cache.bin", "opaque-runtime-state")
        assert workspace.digest != before

        restored = workspace.restore(checkpoint)
        assert restored == before
        assert not workspace.resolve_repo_path("ignored/cache.bin").exists()
        workspace.release_checkpoint(checkpoint)
    finally:
        workspace.close()


def test_empty_directory_is_part_of_workspace_digest(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    workspace = RepositoryWorkspace.create(source_repo=repo, revision="HEAD", workspace_root=tmp_path / "workspace")
    try:
        before = workspace.digest
        workspace.resolve_repo_path("empty-runtime-state").mkdir()
        assert workspace.digest != before
    finally:
        workspace.close()


def test_checkpoint_is_bound_to_its_origin_workspace(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    first = RepositoryWorkspace.create(source_repo=repo, revision="HEAD", workspace_root=tmp_path / "w1")
    second = RepositoryWorkspace.create(source_repo=repo, revision="HEAD", workspace_root=tmp_path / "w2")
    try:
        _claim(first, "execution-first")
        checkpoint = first.checkpoint(label="origin")
        with pytest.raises(PermissionError, match="different workspace"):
            second.restore(checkpoint)
    finally:
        first.close()
        second.close()


def test_close_cleans_checkpoint_snapshots(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    workspace = RepositoryWorkspace.create(source_repo=repo, revision="HEAD", workspace_root=tmp_path / "workspace")
    _claim(workspace)
    checkpoint = workspace.checkpoint(label="cleanup")
    assert isinstance(checkpoint, WorkspaceCheckpoint)
    assert checkpoint.snapshot_root.exists()

    workspace.close()
    assert not checkpoint.snapshot_root.exists()
