from __future__ import annotations

import ast
import json
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from nolane.core.canonical_digest import canonical_digest


_PUBLIC_SYMBOLS = (
    "WorkspaceReceipt",
    "WorkspaceCommandResult",
    "CommandRunner",
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


class _RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path]] = []

    def run(self, command: list[str], *, cwd: Path):
        from nolane.external_core.execution_workspace import WorkspaceCommandResult

        self.calls.append((list(command), cwd))
        return WorkspaceCommandResult(exit_code=0, stdout="ok", stderr="")


def test_wave5s_workspace_prepare_run_cleanup_preserves_accepted_behavior(tmp_path: Path) -> None:
    from nolane.external_core.execution_workspace import RepositoryWorkspace

    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "payload.txt").write_text("accepted-workspace-payload", encoding="utf-8")
    work_root = tmp_path / "work"
    work_root.mkdir()
    runner = _RecordingRunner()
    workspace = RepositoryWorkspace(
        source_root=source_root,
        command_runner=runner,
        work_root=work_root,
    )

    receipt = workspace.prepare(request_id="request-17", task_id="task-5s")
    workspace_root = Path(receipt.workspace_root)
    expected_workspace_id = canonical_digest(
        {
            "request_id": "request-17",
            "source_root": str(source_root.resolve()),
            "task_id": "task-5s",
        }
    )[:20]

    assert workspace.source_root == source_root.resolve()
    assert receipt.workspace_id == expected_workspace_id
    assert receipt.source_root == str(source_root.resolve())
    assert workspace_root.parent.parent == work_root.resolve()
    assert (workspace_root / "payload.txt").read_text(encoding="utf-8") == "accepted-workspace-payload"

    result = workspace.run(receipt, command=["python", "-V"])
    assert result.exit_code == 0
    assert result.stdout == "ok"
    assert result.stderr == ""
    assert runner.calls == [(["python", "-V"], workspace_root)]

    parent = workspace_root.parent
    workspace.cleanup(receipt)
    assert not parent.exists()


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
    assert len(non_native) == 27


def test_wave5s_current_status_tracks_execution_workspace_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")

    assert "Wave 5S" in status
    assert (
        "`external.execution.workspace` -> native `nolane.external_core.execution_workspace`"
        in status
    )
