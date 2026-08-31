from __future__ import annotations

import inspect
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import (
    ActionPhase,
    ActingProtocolLedger,
    EffectClass,
    ExecutionRisk,
    LeaseExpired,
    VerifierLevel,
)
from nolane.external_core.acting_runtime import TransactionalExternalCoreExecutor
from nolane.external_core.execution import OrganizationExecutionControlPlane
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
    repo = tmp_path / "source"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "acting-runtime@example.invalid")
    _git(repo, "config", "user.name", "Acting Runtime")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return RepositoryWorkspace.create(source_repo=repo, revision="HEAD", workspace_root=tmp_path / "workspace")


@dataclass(frozen=True)
class _Receipt:
    receipt_id: str
    agent_id: str
    task_id: str
    tool_id: str
    operation: str
    input_digest: str
    authorized: bool
    success: bool
    failure_kind: str | None
    before_workspace_digest: str
    after_workspace_digest: str
    output_artifact_ids: tuple[str, ...]
    evidence_artifact_id: str
    core_contract_digest: str
    workspace_epoch_id: str


class _MutatingExecutor:
    def __init__(self, *, success: bool) -> None:
        self.success = success
        self.calls = 0
        self._receipts: dict[str, _Receipt] = {}

    def invoke(self, *, workspace: RepositoryWorkspace, action: ToolAction, **kwargs: object) -> _Receipt:
        self.calls += 1
        before = workspace.digest
        workspace.write_text(str(action.arguments["path"]), str(action.arguments["content"]))
        receipt = _Receipt(
            receipt_id=f"core-receipt-{self.calls}",
            agent_id=str(kwargs["agent_id"]),
            task_id=str(kwargs["task_id"]),
            tool_id=action.tool_id,
            operation=action.operation,
            input_digest=canonical_digest(action.to_state()),
            authorized=True,
            success=self.success,
            failure_kind=None if self.success else "simulated_failure",
            before_workspace_digest=before,
            after_workspace_digest=workspace.digest,
            output_artifact_ids=(f"artifact-{self.calls}",),
            evidence_artifact_id=f"evidence-{self.calls}",
            core_contract_digest=str(kwargs["core_contract_digest"]),
            workspace_epoch_id=str(kwargs["workspace_epoch_id"]),
        )
        self._receipts[receipt.receipt_id] = receipt
        return receipt

    def get_receipt(self, receipt_id: str) -> _Receipt:
        return self._receipts[receipt_id]


class _SleepingReadExecutor:
    def __init__(self, *, sleep_seconds: float) -> None:
        self.sleep_seconds = float(sleep_seconds)
        self.calls = 0
        self._receipts: dict[str, _Receipt] = {}

    def invoke(
        self,
        *,
        agent_id: str,
        task_id: str,
        workspace: RepositoryWorkspace,
        action: ToolAction,
        core_contract_digest: str,
        workspace_epoch_id: str,
        **_: object,
    ) -> _Receipt:
        self.calls += 1
        before = workspace.digest
        time.sleep(self.sleep_seconds)
        receipt = _Receipt(
            receipt_id=f"read-receipt-{self.calls}",
            agent_id=str(agent_id),
            task_id=str(task_id),
            tool_id=action.tool_id,
            operation=action.operation,
            input_digest=canonical_digest(action.to_state()),
            authorized=True,
            success=True,
            failure_kind=None,
            before_workspace_digest=before,
            after_workspace_digest=workspace.digest,
            output_artifact_ids=(),
            evidence_artifact_id=f"read-evidence-{self.calls}",
            core_contract_digest=str(core_contract_digest),
            workspace_epoch_id=str(workspace_epoch_id),
        )
        self._receipts[receipt.receipt_id] = receipt
        return receipt

    def get_receipt(self, receipt_id: str) -> _Receipt:
        return self._receipts[receipt_id]


def _epoch(workspace: RepositoryWorkspace) -> str:
    return workspace.active_execution_epoch_id or workspace.claim_execution_epoch("test-acting-runtime")


def _invoke(
    kernel: TransactionalExternalCoreExecutor,
    workspace: RepositoryWorkspace,
    *,
    now_ms: int = 100,
    verifier_level: VerifierLevel = VerifierLevel.V2,
    postcondition_evidence_refs: tuple[str, ...] = ("evidence:workspace-observed", "evidence:receipt-persisted"),
):
    return kernel.invoke(
        agent_id="nolane.coder",
        task_id="task-1",
        workspace=workspace,
        action=ToolAction.from_arguments("filesystem", "write_text", {"path": "README.md", "content": "changed\n"}),
        risk_class=ExecutionRisk.R2,
        effect_class=EffectClass.LOCAL_MUTATION,
        required_capabilities=("filesystem.write",),
        capability_grants=("filesystem.write",),
        authorization_ref="authorization:upstream-decision",
        preconditions=("task-lease-valid", "mutation-scope-covered"),
        precondition_evidence_refs=("evidence:task-lease", "evidence:claim"),
        postconditions=("workspace-observed", "receipt-persisted"),
        postcondition_evidence_refs=postcondition_evidence_refs,
        verifier_level=verifier_level,
        idempotency_key="task-1:write-readme:v1",
        recovery_plan="restore isolated workspace checkpoint",
        core_contract_digest="",
        workspace_epoch_id=_epoch(workspace),
        now_ms=now_ms,
        lease_ttl_ms=10_000,
    )


def test_successful_local_effect_is_committed_only_after_postcondition_verification(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    protocol = ActingProtocolLedger()
    raw = _MutatingExecutor(success=True)
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)
    try:
        result = _invoke(kernel, workspace)
        assert result.record.phase is ActionPhase.COMMITTED
        assert result.replayed is False
        assert workspace.read_text("README.md") == "changed\n"
        assert raw.calls == 1
        assert protocol.validate_chain(result.record.action_id)
    finally:
        workspace.close()


def test_failed_local_effect_restores_bytes_and_records_rollback(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    before = workspace.digest
    protocol = ActingProtocolLedger()
    raw = _MutatingExecutor(success=False)
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)
    try:
        result = _invoke(kernel, workspace)
        assert result.record.phase is ActionPhase.ROLLED_BACK
        assert result.record.commit_ref == ""
        assert workspace.digest == before
        assert workspace.read_text("README.md") == "base\n"
        assert raw.calls == 1
    finally:
        workspace.close()


def test_committed_idempotency_replay_does_not_execute_side_effect_twice(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    protocol = ActingProtocolLedger()
    raw = _MutatingExecutor(success=True)
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)
    try:
        first = _invoke(kernel, workspace, now_ms=100)
        second = _invoke(kernel, workspace, now_ms=200)
        assert first.record.action_id == second.record.action_id
        assert second.replayed is True
        assert raw.calls == 1
        assert workspace.read_text("README.md") == "changed\n"
    finally:
        workspace.close()


def test_insufficient_verifier_is_rejected_before_any_effect(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    protocol = ActingProtocolLedger()
    raw = _MutatingExecutor(success=True)
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)
    try:
        with pytest.raises(PermissionError, match="R2 postcondition verification requires V2"):
            _invoke(kernel, workspace, verifier_level=VerifierLevel.V1)
        assert raw.calls == 0
        assert workspace.read_text("README.md") == "base\n"
    finally:
        workspace.close()


def test_core_receipt_evidence_satisfies_declared_postcondition_evidence(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    protocol = ActingProtocolLedger()
    raw = _MutatingExecutor(success=True)
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)
    try:
        result = _invoke(kernel, workspace, postcondition_evidence_refs=())
        assert result.record.phase is ActionPhase.COMMITTED
        assert "evidence-1" in result.record.postcondition_evidence_refs
    finally:
        workspace.close()


def test_elapsed_core_time_can_expire_lease_before_commit(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    protocol = ActingProtocolLedger()
    raw = _SleepingReadExecutor(sleep_seconds=0.12)
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)
    epoch_id = _epoch(workspace)
    try:
        with pytest.raises(LeaseExpired):
            kernel.invoke(
                agent_id="nolane.coder",
                task_id="task-lease-expiry",
                workspace=workspace,
                action=ToolAction.from_arguments("filesystem", "read_text", {"path": "README.md"}),
                risk_class=ExecutionRisk.R1,
                effect_class=EffectClass.READ,
                required_capabilities=("filesystem.read",),
                capability_grants=("filesystem.read",),
                authorization_ref="authorization:lease-expiry",
                preconditions=("task-lease-valid",),
                precondition_evidence_refs=("evidence:task-lease",),
                postconditions=("core-outcome-evidenced",),
                postcondition_evidence_refs=(),
                verifier_level=VerifierLevel.V1,
                idempotency_key="task-lease-expiry:read:v1",
                core_contract_digest="",
                workspace_epoch_id=epoch_id,
                now_ms=1_000,
                lease_ttl_ms=50,
            )
        assert raw.calls == 1
        assert protocol.records()[0].phase is ActionPhase.ROLLED_BACK
    finally:
        workspace.close()


def test_canonical_organization_control_plane_cannot_bypass_transactional_acting() -> None:
    source = inspect.getsource(OrganizationExecutionControlPlane.step)
    assert "self.acting_executor.invoke(" in source
    assert "self.executor.invoke(" not in source


def test_organization_control_plane_persists_transactional_ledger_state() -> None:
    source = inspect.getsource(OrganizationExecutionControlPlane.to_state)
    restore_source = inspect.getsource(OrganizationExecutionControlPlane.from_state)
    assert "acting_executor" in source
    assert "TransactionalExternalCoreExecutor.from_state" in restore_source


def test_canonical_adapter_delegates_effect_risk_and_verifier_authority_to_transactional_runtime() -> None:
    source = inspect.getsource(OrganizationExecutionControlPlane.step)
    assert "effect_class = self.acting_executor.minimum_effect_class(action.tool_action)" in source
    assert "risk_class = minimum_risk_for_effect(effect_class)" in source
    assert "verifier_level = self.acting_executor.protocol.minimum_verifier_level(risk_class)" in source
    assert "verifier_level=verifier_level" in source


def test_canonical_adapter_does_not_reintroduce_parallel_effect_classifier() -> None:
    source = inspect.getsource(OrganizationExecutionControlPlane.step)
    assert "unconfined_process_tools" not in source
    assert "elif action.tool_action.mutation_paths" not in source
    assert "self.acting_executor.minimum_effect_class(action.tool_action)" in source
