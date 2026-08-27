from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


_PUBLIC_SYMBOLS = (
    "ExecutionToolFailure",
    "CoreInvocationReceipt",
    "ExternalCoreExecutor",
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _workspace(tmp_path: Path):
    from nolane.external_core.execution_workspace import RepositoryWorkspace

    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "test@example.com")
    _git(source, "config", "user.name", "Nolane Test")
    (source / "app.txt").write_text("base\n", encoding="utf-8")
    _git(source, "add", "app.txt")
    _git(source, "commit", "-m", "base")
    revision = _git(source, "rev-parse", "HEAD")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision=revision,
        workspace_root=tmp_path / "isolated",
    )


def test_wave5w_canonical_execution_executor_owns_public_implementation() -> None:
    import nolane.external_core.execution_executor as canonical

    assert all(
        getattr(canonical, name).__module__ == "nolane.external_core.execution_executor"
        for name in _PUBLIC_SYMBOLS
    )
    assert canonical.COMPONENT_ID == "external.execution.executor"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.execution_tools"


def test_wave5w_historical_execution_tools_is_exact_public_object_bridge() -> None:
    import cogcoder.organization.execution_tools as legacy
    import nolane.external_core.execution_executor as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5w_canonical_executor_has_only_canonical_runtime_dependencies() -> None:
    import nolane.external_core.execution_executor as canonical

    source_path = Path(canonical.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    historical: list[str] = []
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
                if alias.name.startswith("cogcoder.organization"):
                    historical.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.add(module)
            if module.startswith("cogcoder.organization"):
                historical.append(f"from:{node.lineno}:{module}")

    assert historical == []
    assert {
        "nolane.core.canonical_digest",
        "nolane.external_core.artifacts",
        "nolane.external_core.coding_claims",
        "nolane.external_core.coding_patches",
        "nolane.external_core.execution_types",
        "nolane.external_core.execution_workspace",
        "nolane.external_core.invokable",
        "nolane.organization.identity",
    }.issubset(imports)


def test_wave5w_executor_preserves_fail_closed_lease_and_mirrored_receipt(tmp_path: Path) -> None:
    from cogcoder.organization.runtime import OrganizationRuntime
    from nolane.external_core.execution_executor import CoreInvocationReceipt, ExternalCoreExecutor
    from nolane.external_core.execution_types import ToolAction

    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task("task-5w", title="executor cutover", plan_node_id="P1")
    workspace = _workspace(tmp_path)
    executor = ExternalCoreExecutor(
        registry=runtime.registry,
        external_cores=runtime.external_cores,
        artifacts=runtime.artifacts,
        coding_patches=runtime.coding.patches,
        code_claims=runtime.coding.claims,
    )

    no_lease = executor.invoke(
        agent_id="coding.backend.01",
        task_id="task-5w",
        workspace=workspace,
        action=ToolAction.from_arguments("filesystem", "read_text", {"path": "app.txt"}),
    )
    assert no_lease.success is False
    assert no_lease.authorized is True
    assert no_lease.failure_kind == "task_lease_required"
    assert CoreInvocationReceipt.from_state(no_lease.to_state()) == no_lease

    runtime.tasks.lease("task-5w", "coding.backend.01")
    success = executor.invoke(
        agent_id="coding.backend.01",
        task_id="task-5w",
        workspace=workspace,
        action=ToolAction.from_arguments("filesystem", "read_text", {"path": "app.txt"}),
    )
    assert success.success is True
    assert success.mirrored_tool_receipt_id is not None
    mirrored = runtime.coding.patches.get_tool_receipt(success.mirrored_tool_receipt_id)
    assert mirrored.success is True
    assert runtime.artifacts.get(success.output_artifact_ids[0]).content == "base\n"
    workspace.close()


def test_wave5w_executor_authority_version_facade_and_debt_cutover() -> None:
    implementation = build_component_implementation_ledger()
    row = implementation["external.execution.executor"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.execution_executor"
    assert row.legacy_sources == ("cogcoder/organization/execution_tools.py",)
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.execution.executor")) == "0.0.1"
    assert all(
        binding.component_id != "external.execution.executor"
        for binding in build_active_facade_bindings()
    )

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    serialized = json.dumps(state, sort_keys=True)
    assert "external.execution.executor" not in serialized

    non_native = [
        record
        for record in implementation.values()
        if record.status is not ImplementationStatus.CANONICAL_NATIVE
    ]
    assert len(non_native) <= 24


def test_wave5w_current_status_tracks_native_executor_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")

    assert "Wave 5W" in status
    assert "`external.execution.executor` -> native `nolane.external_core.execution_executor`" in status
    assert "25" in status and "24" in status
