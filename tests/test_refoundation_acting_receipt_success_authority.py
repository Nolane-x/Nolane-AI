from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import (
    ActionPhase,
    ActingProtocolLedger,
    EffectClass,
    ExecutionRisk,
    VerifierLevel,
)
from nolane.external_core.acting_runtime import TransactionalExternalCoreExecutor
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
    _git(repo, "config", "user.email", "receipt-authority@example.invalid")
    _git(repo, "config", "user.name", "Receipt Authority")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=repo,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


@dataclass(frozen=True)
class _Receipt:
    receipt_id: str
    agent_id: str
    task_id: str
    tool_id: str
    operation: str
    input_digest: str
    authorized: bool
    success: object
    failure_kind: str | None
    before_workspace_digest: str
    after_workspace_digest: str
    output_artifact_ids: tuple[str, ...]
    evidence_artifact_id: str
    core_contract_digest: str
    workspace_epoch_id: str


class _NonBooleanFailureExecutor:
    def __init__(self) -> None:
        self.calls = 0

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
        workspace.write_text(str(action.arguments["path"]), str(action.arguments["content"]))
        return _Receipt(
            receipt_id=f"non-boolean-receipt-{self.calls}",
            agent_id=str(agent_id),
            task_id=str(task_id),
            tool_id=action.tool_id,
            operation=action.operation,
            input_digest=canonical_digest(action.to_state()),
            authorized=True,
            success="false",
            failure_kind="simulated_failure",
            before_workspace_digest=before,
            after_workspace_digest=workspace.digest,
            output_artifact_ids=(),
            evidence_artifact_id=f"non-boolean-evidence-{self.calls}",
            core_contract_digest=str(core_contract_digest),
            workspace_epoch_id=str(workspace_epoch_id),
        )

    def get_receipt(self, receipt_id: str) -> _Receipt:
        raise KeyError(receipt_id)


def test_non_boolean_failure_receipt_cannot_commit_local_effect(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    before = workspace.digest
    protocol = ActingProtocolLedger()
    raw = _NonBooleanFailureExecutor()
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)
    epoch_id = workspace.claim_execution_epoch("receipt-success-authority")
    action = ToolAction.from_arguments(
        "filesystem",
        "write_text",
        {"path": "README.md", "content": "should-rollback\n"},
    )

    try:
        with pytest.raises(ValueError, match="core receipt provenance mismatch: success"):
            kernel.invoke(
                agent_id="nolane.coder",
                task_id="task-receipt-success-authority",
                workspace=workspace,
                action=action,
                risk_class=ExecutionRisk.R2,
                effect_class=EffectClass.LOCAL_MUTATION,
                required_capabilities=("filesystem.write",),
                capability_grants=("filesystem.write",),
                authorization_ref="authorization:receipt-success-authority",
                preconditions=("task-lease-valid",),
                precondition_evidence_refs=("evidence:task-lease",),
                postconditions=("receipt-success-canonical",),
                postcondition_evidence_refs=(),
                verifier_level=VerifierLevel.V2,
                idempotency_key="receipt-success-authority:v1",
                recovery_plan="restore isolated workspace checkpoint",
                core_contract_digest="",
                workspace_epoch_id=epoch_id,
                now_ms=1_000,
                lease_ttl_ms=10_000,
            )
        assert raw.calls == 1
        assert protocol.records()[0].phase is ActionPhase.ROLLED_BACK
        assert workspace.digest == before
        assert workspace.read_text("README.md") == "base\n"
    finally:
        workspace.close()
