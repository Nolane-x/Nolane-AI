from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


_PUBLIC_SYMBOLS = (
    "WorkspaceCommandResult",
    "RepositoryWorkspace",
)


def test_wave5s_canonical_execution_workspace_owns_complete_public_implementation() -> None:
    import nolane.external_core.execution_workspace as canonical

    assert all(
        getattr(canonical, name).__module__ == "nolane.external_core.execution_workspace"
        for name in _PUBLIC_SYMBOLS
    )
    assert canonical.COMPONENT_ID == "external.execution.workspace"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.execution_workspace"


def test_wave5s_historical_execution_workspace_is_exact_public_object_bridge() -> None:
    import cogcoder.organization.execution_workspace as legacy
    import nolane.external_core.execution_workspace as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5s_canonical_execution_workspace_has_no_reverse_authority_import() -> None:
    import nolane.external_core.execution_workspace as canonical

    source_path = Path(canonical.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    has_native_digest_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cogcoder.organization.execution_workspace" or alias.name.startswith(
                    "cogcoder.organization.execution_workspace."
                ):
                    offenders.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "cogcoder.organization.execution_workspace" or module.startswith(
                "cogcoder.organization.execution_workspace."
            ):
                offenders.append(f"from:{node.lineno}:{module}")
            if module == "nolane.core.canonical_digest" and any(
                alias.name == "canonical_digest" for alias in node.names
            ):
                has_native_digest_import = True

    assert offenders == [], (
        "canonical execution-workspace authority reverse-imports historical implementation: "
        + "; ".join(offenders)
    )
    assert has_native_digest_import, (
        "canonical execution-workspace implementation must depend on native canonical digest authority"
    )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _accepted_repository(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", str(source)], check=True, text=True, capture_output=True)
    _git(source, "config", "user.email", "wave5s@example.invalid")
    _git(source, "config", "user.name", "Wave 5S")
    (source / "payload.txt").write_text("accepted-workspace-payload\n", encoding="utf-8")
    _git(source, "add", "payload.txt")
    _git(source, "commit", "-m", "accepted fixture")
    return source, _git(source, "rev-parse", "HEAD")


def test_wave5s_workspace_git_worktree_behavior_is_preserved(tmp_path: Path) -> None:
    from nolane.external_core.execution_workspace import RepositoryWorkspace

    source, revision = _accepted_repository(tmp_path)
    target = tmp_path / "isolated" / "repo"
    workspace = RepositoryWorkspace.create(
        source_repo=source,
        revision=revision,
        workspace_root=target,
    )

    assert workspace.source_repo == source.resolve()
    assert workspace.root == target.resolve()
    assert workspace.base_revision == revision
    assert workspace.read_text("payload.txt") == "accepted-workspace-payload\n"

    initial_digest = workspace.digest
    workspace.write_text("nested/new.txt", "alpha")
    workspace.append_text("nested/new.txt", "-beta")
    assert workspace.read_text("nested/new.txt") == "alpha-beta"
    assert workspace.digest != initial_digest

    with pytest.raises(PermissionError, match="path escapes isolated workspace"):
        workspace.resolve_repo_path("../escape.txt")

    result = workspace.run_argv(
        ["python", "-c", "print('wave5s-workspace-ok')"],
        timeout_seconds=10.0,
        max_output_chars=1_000,
    )
    assert result.argv == ("python", "-c", "print('wave5s-workspace-ok')")
    assert result.returncode == 0
    assert result.stdout.strip() == "wave5s-workspace-ok"
    assert result.stderr == ""
    assert not result.timed_out

    workspace.close()
    assert not target.exists()
    with pytest.raises(RuntimeError, match="repository workspace is closed"):
        workspace.read_text("payload.txt")


def test_wave5s_execution_workspace_component_version_and_authority_cutover() -> None:
    implementation = build_component_implementation_ledger()
    row = implementation["external.execution.workspace"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.execution_workspace"
    assert row.legacy_sources == ("cogcoder/organization/execution_workspace.py",)
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.execution.workspace")) == "0.0.1"

    facade_ids = {binding.component_id for binding in build_active_facade_bindings()}
    assert "external.execution.workspace" not in facade_ids


def test_wave5s_generated_native_debt_no_longer_contains_execution_workspace() -> None:
    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    serialized = json.dumps(state, sort_keys=True)
    assert "external.execution.workspace" not in serialized

    implementation = build_component_implementation_ledger()
    non_native = [
        row
        for row in implementation.values()
        if row.status is not ImplementationStatus.CANONICAL_NATIVE
    ]
    assert len(non_native) <= 27


def test_wave5s_current_status_tracks_execution_workspace_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")

    assert "Wave 5S" in status
    assert (
        "`external.execution.workspace` -> native `nolane.external_core.execution_workspace`"
        in status
    )
