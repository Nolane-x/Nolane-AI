from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from nolane.external_core.acting_runtime import TransactionalExternalCoreExecutor
from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    ExecutionStepReceipt,
    OrganizationExecutionControlPlane,
)
from nolane.external_core.execution_types import ExecutionBudget
from nolane.external_core.execution_workspace import RepositoryWorkspace
from nolane.external_core.invokable import ExternalCoreRegistry, ExternalCoreSpec
from nolane.neural.inference_bridge import CognitiveStateEncoder


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _source_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "source"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "session-proof@example.invalid")
    _git(repo, "config", "user.name", "Session Proof")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return repo


def _workspace(source: Path, root: Path) -> RepositoryWorkspace:
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=root,
    )


def _core(core_id: str, version: str = "1") -> ExternalCoreSpec:
    return ExternalCoreSpec(
        core_id=core_id,
        owner_agent_or_region="proof-region",
        capabilities=(core_id.replace("-", "_"),),
        input_schema="mapping-v1",
        output_schema="mapping-v1",
        side_effects=(),
        required_permissions=("external_core.invoke",),
        cost_model="bounded",
        failure_modes=("unavailable",),
        verification_hooks=("receipt",),
        version=version,
    )


def _external_cores() -> ExternalCoreRegistry:
    registry = ExternalCoreRegistry()
    registry.register(_core("proof-core"))
    return registry


@dataclass(frozen=True)
class _Identity:
    agent_id: str = "agent-1"
    status: str = "active"
    tool_permissions: tuple[str, ...] = ("filesystem",)
    external_core_bindings: tuple[str, ...] = ("proof-core",)

    def to_state(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "tool_permissions": list(self.tool_permissions),
            "external_core_bindings": list(self.external_core_bindings),
        }


@dataclass(frozen=True)
class _Task:
    task_id: str = "task-1"
    leased_to: str = "agent-1"
    aborted_by: str | None = None
    abort_reason: str = ""
    completed_by: str | None = None

    def to_state(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "leased_to": self.leased_to,
            "aborted_by": self.aborted_by,
            "abort_reason": self.abort_reason,
        }


class _Registry:
    def __init__(self) -> None:
        self.identity = _Identity()

    def get(self, agent_id: str) -> _Identity:
        if str(agent_id) != self.identity.agent_id:
            raise KeyError(agent_id)
        return self.identity


class _Tasks:
    def __init__(self) -> None:
        self.task = _Task()

    def get(self, task_id: str) -> _Task:
        if str(task_id) != self.task.task_id:
            raise KeyError(task_id)
        return self.task


class _ContextMustNotRun:
    def compile(self, *_: object, **__: object):
        raise AssertionError("execution proof preflight must happen before context/inference")


class _Artifacts:
    def __init__(self) -> None:
        self.counter = 0

    def put(self, **_: object):
        self.counter += 1
        return SimpleNamespace(artifact_id=f"artifact-{self.counter}")


class _RawExecutor:
    external_core_ids = frozenset()

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, **_: object):
        self.calls += 1
        raise AssertionError("session proof tests must fail before concrete dispatch")

    def get_receipt(self, receipt_id: str):
        raise KeyError(receipt_id)

    def to_state(self) -> dict[str, object]:
        return {"receipts": []}


class _Backend:
    backend_id = "backend-proof-v1"
    checkpoint_digest = "checkpoint-proof-v1"

    def __init__(self) -> None:
        self.calls = 0

    def decide(self, _request):
        self.calls += 1
        raise AssertionError("execution proof preflight must happen before inference")


def _plane(external_cores: ExternalCoreRegistry):
    registry = _Registry()
    tasks = _Tasks()
    artifacts = _Artifacts()
    raw = _RawExecutor()
    acting = TransactionalExternalCoreExecutor(executor=raw)
    plane = OrganizationExecutionControlPlane(
        registry=registry,
        tasks=tasks,
        context=_ContextMustNotRun(),
        artifacts=artifacts,
        external_cores=external_cores,
        coding=object(),
        encoder=CognitiveStateEncoder(version="organization-context-digest-v1"),
        executor=raw,
        acting_executor=acting,
    )
    backend = _Backend()
    plane.bind_backend("agent-1", backend)
    return plane, backend, raw


def _budget() -> ExecutionBudget:
    return ExecutionBudget(
        max_steps=4,
        max_tool_calls=2,
        max_external_core_calls=1,
        max_compute_units=4,
    )


def _start(plane: OrganizationExecutionControlPlane, workspace: RepositoryWorkspace) -> ExecutionSession:
    return plane.start(
        agent_id="agent-1",
        task_id="task-1",
        workspace=workspace,
        action_schema=("filesystem.read_text",),
        budget=_budget(),
    )


def test_start_claims_session_epoch_and_pins_external_core_registry(tmp_path: Path) -> None:
    external_cores = _external_cores()
    plane, _backend, _raw = _plane(external_cores)
    source = _source_repo(tmp_path)
    workspace = _workspace(source, tmp_path / "workspace")
    try:
        session = _start(plane, workspace)
        assert session.execution_proof_version == 2
        assert session.external_core_registry_digest == external_cores.contract_digest
        assert session.workspace_epoch_id == workspace.active_execution_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id
        assert session.workspace_epoch_id
    finally:
        workspace.close()


def test_second_live_session_cannot_claim_same_workspace_epoch(tmp_path: Path) -> None:
    plane, _backend, _raw = _plane(_external_cores())
    source = _source_repo(tmp_path)
    workspace = _workspace(source, tmp_path / "workspace")
    try:
        first = _start(plane, workspace)
        assert workspace.active_execution_epoch_owner == first.session_id
        with pytest.raises(PermissionError, match="owned by another execution session"):
            _start(plane, workspace)
    finally:
        workspace.close()


def test_external_core_registry_drift_fails_before_context_or_inference(tmp_path: Path) -> None:
    external_cores = _external_cores()
    plane, backend, raw = _plane(external_cores)
    source = _source_repo(tmp_path)
    workspace = _workspace(source, tmp_path / "workspace")
    try:
        session = _start(plane, workspace)
        external_cores.register(_core("proof-core-2"))
        with pytest.raises(RuntimeError, match="external core registry.*persisted execution session"):
            plane.step(session.session_id)
        assert backend.calls == 0
        assert raw.calls == 0
        assert plane.get_session(session.session_id).decision_receipt_ids == ()
    finally:
        workspace.close()


def test_attach_workspace_rebinds_exact_persisted_epoch(tmp_path: Path) -> None:
    plane, _backend, _raw = _plane(_external_cores())
    source = _source_repo(tmp_path)
    first_workspace = _workspace(source, tmp_path / "workspace-a")
    second_workspace = _workspace(source, tmp_path / "workspace-b")
    try:
        session = _start(plane, first_workspace)
        epoch_id = session.workspace_epoch_id
        first_workspace.release_execution_epoch(session.session_id, epoch_id)
        assert second_workspace.active_execution_epoch_id is None
        plane.attach_workspace(session.session_id, second_workspace)
        assert second_workspace.active_execution_epoch_id == epoch_id
        assert second_workspace.active_execution_epoch_owner == session.session_id
    finally:
        first_workspace.close()
        second_workspace.close()


def test_terminal_transition_releases_session_epoch(tmp_path: Path) -> None:
    plane, _backend, _raw = _plane(_external_cores())
    source = _source_repo(tmp_path)
    workspace = _workspace(source, tmp_path / "workspace")
    try:
        session = _start(plane, workspace)
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        plane._terminal(session, ExecutionState.FAILED, "proof fixture terminal")
        assert workspace.active_execution_epoch_id is None
        assert workspace.active_execution_epoch_owner is None
    finally:
        workspace.close()


def test_modern_session_state_cannot_downgrade_by_stripping_proof_fields(tmp_path: Path) -> None:
    plane, _backend, _raw = _plane(_external_cores())
    source = _source_repo(tmp_path)
    workspace = _workspace(source, tmp_path / "workspace")
    try:
        session = _start(plane, workspace)
        state = session.to_state()
        assert state["execution_proof_version"] == 2
        assert ExecutionSession.from_state(state) == session
        for field in ("external_core_registry_digest", "workspace_epoch_id"):
            corrupted = dict(state)
            corrupted.pop(field)
            with pytest.raises(ValueError, match="execution proof"):
                ExecutionSession.from_state(corrupted)
    finally:
        workspace.close()


def test_step_receipt_digest_binds_core_contract_and_workspace_epoch() -> None:
    baseline = ExecutionStepReceipt.create(
        session_id="execution-00000001",
        step_index=0,
        decision_receipt_id="decision-1",
        core_receipt_id="core-1",
        before_workspace_digest="before",
        after_workspace_digest="after",
        state_after=ExecutionState.RUNNING,
        output_artifact_ids=("artifact-1",),
        core_contract_digest="core-contract-a",
        workspace_epoch_id="workspace-epoch-a",
    )
    different_core = ExecutionStepReceipt.create(
        session_id="execution-00000001",
        step_index=0,
        decision_receipt_id="decision-1",
        core_receipt_id="core-1",
        before_workspace_digest="before",
        after_workspace_digest="after",
        state_after=ExecutionState.RUNNING,
        output_artifact_ids=("artifact-1",),
        core_contract_digest="core-contract-b",
        workspace_epoch_id="workspace-epoch-a",
    )
    different_epoch = ExecutionStepReceipt.create(
        session_id="execution-00000001",
        step_index=0,
        decision_receipt_id="decision-1",
        core_receipt_id="core-1",
        before_workspace_digest="before",
        after_workspace_digest="after",
        state_after=ExecutionState.RUNNING,
        output_artifact_ids=("artifact-1",),
        core_contract_digest="core-contract-a",
        workspace_epoch_id="workspace-epoch-b",
    )
    assert baseline.digest != different_core.digest
    assert baseline.digest != different_epoch.digest
    assert ExecutionStepReceipt.from_state(baseline.to_state()) == baseline
