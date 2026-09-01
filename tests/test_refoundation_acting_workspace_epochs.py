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


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "acting-epochs@example.invalid")
    _git(repo, "config", "user.name", "Acting Epoch Tests")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return repo


def _workspace(tmp_path: Path) -> RepositoryWorkspace:
    return RepositoryWorkspace.create(
        source_repo=_repository(tmp_path),
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def test_checkpoint_requires_active_execution_epoch(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="execution epoch"):
            workspace.checkpoint(label="without-authority")
    finally:
        workspace.close()


def test_workspace_rejects_second_live_execution_epoch_owner(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    try:
        first_epoch = workspace.claim_execution_epoch("execution-00000001")
        assert first_epoch == workspace.active_execution_epoch_id
        assert workspace.claim_execution_epoch("execution-00000001") == first_epoch

        with pytest.raises(PermissionError, match="execution epoch"):
            workspace.claim_execution_epoch("execution-00000002")
    finally:
        workspace.close()


def test_released_execution_epoch_cannot_be_reclaimed_as_same_generation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    try:
        first_epoch = workspace.claim_execution_epoch("execution-00000001")
        workspace.release_execution_epoch("execution-00000001", first_epoch)

        second_epoch = workspace.claim_execution_epoch("execution-00000001")
        assert second_epoch != first_epoch
        assert second_epoch == workspace.active_execution_epoch_id
    finally:
        workspace.close()


def test_checkpoint_from_released_epoch_cannot_restore_in_new_epoch(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    try:
        epoch_a = workspace.claim_execution_epoch("execution-00000001")
        checkpoint = workspace.checkpoint(label="epoch-a")
        workspace.write_text("README.md", "epoch-a-mutated\n")
        workspace.release_execution_epoch("execution-00000001", epoch_a)

        epoch_b = workspace.claim_execution_epoch("execution-00000002")
        assert epoch_b != epoch_a

        with pytest.raises(PermissionError, match="checkpoint.*epoch"):
            workspace.restore(checkpoint)
    finally:
        workspace.close()


def test_restored_epoch_can_bind_exact_persisted_epoch_on_fresh_workspace(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    try:
        persisted_epoch = "workspace-epoch-persisted-authority"
        restored = workspace.claim_execution_epoch(
            "execution-00000001",
            expected_epoch_id=persisted_epoch,
        )
        assert restored == persisted_epoch
        assert workspace.active_execution_epoch_id == persisted_epoch
    finally:
        workspace.close()
