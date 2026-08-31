from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.execution_executor import ExternalCoreExecutor
from nolane.external_core.execution_types import ToolAction
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
    _git(source, "config", "user.email", "core-proof@example.invalid")
    _git(source, "config", "user.name", "Core Proof")
    (source / "README.md").write_text("base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def _external_fixture(tmp_path: Path):
    runtime = OrganizationRuntime.first_generation()
    specs = runtime.external_cores.specs()
    assert specs, "first-generation runtime must expose at least one external core"
    spec = specs[0]
    identity = next(
        row
        for row in runtime.registry.identities()
        if spec.core_id in row.external_core_bindings
    )
    task_id = "task-core-proof"
    runtime.tasks.add_task(task_id, title="core proof continuity", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)

    workspace = _workspace(tmp_path)
    epoch_id = workspace.claim_execution_epoch("execution-core-proof")
    executor = ExternalCoreExecutor(
        registry=runtime.registry,
        external_cores=runtime.external_cores,
        artifacts=runtime.artifacts,
        coding_patches=runtime.coding.patches,
        code_claims=runtime.coding.claims,
    )
    calls: list[dict[str, object]] = []

    def handler(_workspace: RepositoryWorkspace, arguments):
        calls.append(dict(arguments))
        return {"echo": arguments.get("value")}

    executor.register_handler(spec.core_id, handler)
    action = ToolAction.from_arguments(spec.core_id, "probe", {"value": 7})
    return runtime, spec, identity.agent_id, task_id, workspace, epoch_id, executor, action, calls


def test_external_core_receipt_binds_exact_contract_and_workspace_epoch(tmp_path: Path) -> None:
    (
        _runtime,
        spec,
        agent_id,
        task_id,
        workspace,
        epoch_id,
        executor,
        action,
        calls,
    ) = _external_fixture(tmp_path)
    try:
        receipt = executor.invoke(
            agent_id=agent_id,
            task_id=task_id,
            workspace=workspace,
            action=action,
            core_contract_digest=spec.contract_digest,
            workspace_epoch_id=epoch_id,
        )
        assert receipt.success is True
        assert receipt.external_core is True
        assert receipt.core_contract_digest == spec.contract_digest
        assert receipt.workspace_epoch_id == epoch_id
        assert calls == [{"value": 7}]
    finally:
        workspace.close()


def test_external_core_contract_mismatch_fails_before_handler_dispatch(tmp_path: Path) -> None:
    (
        _runtime,
        _spec,
        agent_id,
        task_id,
        workspace,
        epoch_id,
        executor,
        action,
        calls,
    ) = _external_fixture(tmp_path)
    try:
        with pytest.raises(ValueError, match="core contract"):
            executor.invoke(
                agent_id=agent_id,
                task_id=task_id,
                workspace=workspace,
                action=action,
                core_contract_digest="wrong-core-contract-digest",
                workspace_epoch_id=epoch_id,
            )
        assert calls == []
        assert executor.receipts() == ()
    finally:
        workspace.close()


def test_workspace_epoch_mismatch_fails_before_handler_dispatch(tmp_path: Path) -> None:
    (
        _runtime,
        spec,
        agent_id,
        task_id,
        workspace,
        _epoch_id,
        executor,
        action,
        calls,
    ) = _external_fixture(tmp_path)
    try:
        with pytest.raises(PermissionError, match="workspace execution epoch"):
            executor.invoke(
                agent_id=agent_id,
                task_id=task_id,
                workspace=workspace,
                action=action,
                core_contract_digest=spec.contract_digest,
                workspace_epoch_id="workspace-epoch-substituted",
            )
        assert calls == []
        assert executor.receipts() == ()
    finally:
        workspace.close()
