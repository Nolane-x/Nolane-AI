from __future__ import annotations

import subprocess
from dataclasses import dataclass, replace
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
    _git(repo, "config", "user.email", "receipt-provenance@example.invalid")
    _git(repo, "config", "user.name", "Receipt Provenance")
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
    success: bool
    failure_kind: str | None
    before_workspace_digest: str
    after_workspace_digest: str
    output_artifact_ids: tuple[str, ...]
    evidence_artifact_id: str
    core_contract_digest: str
    workspace_epoch_id: str


class _SubstitutingExecutor:
    def __init__(self, mismatch: str) -> None:
        self.mismatch = mismatch
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
        if action.operation == "write_text":
            workspace.write_text(
                str(action.arguments["path"]),
                str(action.arguments["content"]),
            )
        after = workspace.digest
        receipt = _Receipt(
            receipt_id=f"core-substitution-{self.calls}",
            agent_id=str(agent_id),
            task_id=str(task_id),
            tool_id=action.tool_id,
            operation=action.operation,
            input_digest=canonical_digest(action.to_state()),
            authorized=True,
            success=True,
            failure_kind=None,
            before_workspace_digest=before,
            after_workspace_digest=after,
            output_artifact_ids=(f"artifact-{self.calls}",),
            evidence_artifact_id=f"evidence-{self.calls}",
            core_contract_digest=str(core_contract_digest),
            workspace_epoch_id=str(workspace_epoch_id),
        )
        replacements = {
            "agent_id": {"agent_id": "other-agent"},
            "task_id": {"task_id": "other-task"},
            "tool_id": {"tool_id": "git"},
            "operation": {"operation": "append_text"},
            "input_digest": {"input_digest": "wrong-input-digest"},
            "authorized": {"authorized": False},
            "before_workspace_digest": {"before_workspace_digest": "wrong-before"},
            "after_workspace_digest": {"after_workspace_digest": "wrong-after"},
            "core_contract_digest": {"core_contract_digest": "wrong-core-contract"},
            "workspace_epoch_id": {"workspace_epoch_id": "wrong-workspace-epoch"},
        }
        receipt = replace(receipt, **replacements[self.mismatch])
        self._receipts[receipt.receipt_id] = receipt
        return receipt

    def get_receipt(self, receipt_id: str) -> _Receipt:
        return self._receipts[receipt_id]


def _invoke_local(
    kernel: TransactionalExternalCoreExecutor,
    workspace: RepositoryWorkspace,
):
    action = ToolAction.from_arguments(
        "filesystem",
        "write_text",
        {"path": "README.md", "content": "changed\n"},
    )
    epoch_id = workspace.active_execution_epoch_id or workspace.claim_execution_epoch(
        "test-receipt-provenance"
    )
    return kernel.invoke(
        agent_id="nolane.coder",
        task_id="task-1",
        workspace=workspace,
        action=action,
        risk_class=ExecutionRisk.R2,
        effect_class=EffectClass.LOCAL_MUTATION,
        required_capabilities=("filesystem",),
        capability_grants=("filesystem",),
        authorization_ref="decision:receipt-provenance",
        preconditions=("authorized",),
        precondition_evidence_refs=("evidence:pre",),
        postconditions=("core-outcome-evidenced",),
        postcondition_evidence_refs=(),
        verifier_level=VerifierLevel.V2,
        idempotency_key="receipt-provenance:local:v1",
        recovery_plan="restore isolated workspace checkpoint",
        core_contract_digest="",
        workspace_epoch_id=epoch_id,
        now_ms=100,
        lease_ttl_ms=10_000,
    )


@pytest.mark.parametrize(
    "mismatch",
    (
        "agent_id",
        "task_id",
        "tool_id",
        "operation",
        "input_digest",
        "authorized",
        "before_workspace_digest",
        "after_workspace_digest",
        "core_contract_digest",
        "workspace_epoch_id",
    ),
)
def test_local_core_receipt_substitution_fails_closed_and_restores_workspace(
    tmp_path: Path,
    mismatch: str,
) -> None:
    workspace = _workspace(tmp_path)
    before = workspace.digest
    protocol = ActingProtocolLedger()
    raw = _SubstitutingExecutor(mismatch)
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)
    try:
        with pytest.raises(ValueError, match="core receipt provenance mismatch"):
            _invoke_local(kernel, workspace)
        assert raw.calls == 1
        assert workspace.digest == before
        assert workspace.read_text("README.md") == "base\n"
        row = protocol.records()[0]
        assert row.phase is ActionPhase.ROLLED_BACK
        assert row.commit_ref == ""
    finally:
        workspace.close()


def test_valid_core_receipt_still_commits(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    protocol = ActingProtocolLedger()
    raw = _SubstitutingExecutor("tool_id")
    original = raw.invoke

    def valid_invoke(**kwargs: object) -> _Receipt:
        raw.mismatch = "tool_id"
        receipt = original(**kwargs)
        action = kwargs["action"]
        assert isinstance(action, ToolAction)
        return replace(receipt, tool_id=action.tool_id)

    raw.invoke = valid_invoke  # type: ignore[method-assign]
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)
    try:
        result = _invoke_local(kernel, workspace)
        assert result.record.phase is ActionPhase.COMMITTED
        assert workspace.read_text("README.md") == "changed\n"
    finally:
        workspace.close()
