from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.acting_protocol import (
    EffectClass,
    ExecutionContract,
    ExecutionRisk,
    VerifierLevel,
)
from nolane.external_core.acting_runtime import TransactionalExternalCoreExecutor
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


def _contract(*, core_contract_digest: str, workspace_epoch_id: str) -> ExecutionContract:
    return ExecutionContract(
        action_id="acting-action-proof",
        core_id="external.example",
        operation="probe",
        input_digest="input-digest",
        risk_class=ExecutionRisk.R3,
        effect_class=EffectClass.EXTERNAL_MUTATION,
        required_capabilities=("external.example",),
        preconditions=(),
        postconditions=(),
        idempotency_key="proof-continuity",
        recovery_plan="record uncertain external outcome",
        core_contract_digest=core_contract_digest,
        workspace_epoch_id=workspace_epoch_id,
    )


def test_execution_contract_semantic_identity_includes_core_and_epoch_proof() -> None:
    baseline = _contract(
        core_contract_digest="core-contract-a",
        workspace_epoch_id="workspace-epoch-a",
    )
    different_core = _contract(
        core_contract_digest="core-contract-b",
        workspace_epoch_id="workspace-epoch-a",
    )
    different_epoch = _contract(
        core_contract_digest="core-contract-a",
        workspace_epoch_id="workspace-epoch-b",
    )
    assert baseline.semantic_digest != different_core.semantic_digest
    assert baseline.semantic_digest != different_epoch.semantic_digest
    assert ExecutionContract.from_state(baseline.to_state()) == baseline


@dataclass(frozen=True)
class _ProofReceipt:
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


class _SubstitutingProofExecutor:
    def __init__(self, mismatch: str) -> None:
        self.mismatch = mismatch
        self.calls = 0
        self._receipts: dict[str, _ProofReceipt] = {}

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
    ) -> _ProofReceipt:
        self.calls += 1
        receipt = _ProofReceipt(
            receipt_id=f"proof-receipt-{self.calls}",
            agent_id=str(agent_id),
            task_id=str(task_id),
            tool_id=action.tool_id,
            operation=action.operation,
            input_digest=__import__("nolane.core.canonical_digest", fromlist=["canonical_digest"]).canonical_digest(action.to_state()),
            authorized=True,
            success=True,
            failure_kind=None,
            before_workspace_digest=workspace.digest,
            after_workspace_digest=workspace.digest,
            output_artifact_ids=(),
            evidence_artifact_id=f"proof-evidence-{self.calls}",
            core_contract_digest=str(core_contract_digest),
            workspace_epoch_id=str(workspace_epoch_id),
        )
        if self.mismatch == "core_contract_digest":
            receipt = _ProofReceipt(**{**receipt.__dict__, "core_contract_digest": "substituted-core-contract"})
        elif self.mismatch == "workspace_epoch_id":
            receipt = _ProofReceipt(**{**receipt.__dict__, "workspace_epoch_id": "substituted-workspace-epoch"})
        self._receipts[receipt.receipt_id] = receipt
        return receipt

    def get_receipt(self, receipt_id: str) -> _ProofReceipt:
        return self._receipts[receipt_id]


@pytest.mark.parametrize("mismatch", ("core_contract_digest", "workspace_epoch_id"))
def test_transactional_boundary_rejects_substituted_execution_proof(
    tmp_path: Path,
    mismatch: str,
) -> None:
    workspace = _workspace(tmp_path)
    epoch_id = workspace.claim_execution_epoch("execution-proof-substitution")
    raw = _SubstitutingProofExecutor(mismatch)
    kernel = TransactionalExternalCoreExecutor(executor=raw)
    action = ToolAction.from_arguments("external.example", "probe", {"value": 7})
    try:
        with pytest.raises(ValueError, match="core receipt provenance mismatch"):
            kernel.invoke(
                agent_id="nolane.coder",
                task_id="task-proof-substitution",
                workspace=workspace,
                action=action,
                risk_class=ExecutionRisk.R3,
                effect_class=EffectClass.EXTERNAL_MUTATION,
                required_capabilities=("external.example",),
                capability_grants=("external.example",),
                authorization_ref="decision:proof-substitution",
                postconditions=("core-outcome-evidenced",),
                verifier_level=VerifierLevel.V3,
                idempotency_key="proof-substitution:v1",
                recovery_plan="record uncertain external outcome",
                core_contract_digest="core-contract-a",
                workspace_epoch_id=epoch_id,
                now_ms=100,
                lease_ttl_ms=10_000,
            )
        assert raw.calls == 1
    finally:
        workspace.close()
