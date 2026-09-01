from __future__ import annotations

import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import (
    ActionBudget,
    ActionPhase,
    ActingProtocolLedger,
    EffectClass,
    ExecutionContract,
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
    _git(repo, "config", "user.email", "replay-authority@example.invalid")
    _git(repo, "config", "user.name", "Replay Authority")
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


class _Executor:
    def __init__(self) -> None:
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
        workspace.write_text(str(action.arguments["path"]), str(action.arguments["content"]))
        receipt = _Receipt(
            receipt_id=f"core-receipt-{self.calls}",
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
            output_artifact_ids=(f"artifact-{self.calls}",),
            evidence_artifact_id=f"evidence-{self.calls}",
            core_contract_digest=str(core_contract_digest),
            workspace_epoch_id=str(workspace_epoch_id),
        )
        self._receipts[receipt.receipt_id] = receipt
        return receipt

    def get_receipt(self, receipt_id: str) -> _Receipt:
        return self._receipts[receipt_id]


def _action() -> ToolAction:
    return ToolAction.from_arguments(
        "filesystem",
        "write_text",
        {"path": "README.md", "content": "changed\n"},
    )


def _epoch(workspace: RepositoryWorkspace) -> str:
    return workspace.active_execution_epoch_id or workspace.claim_execution_epoch("replay-authority")


def _invoke(
    kernel: TransactionalExternalCoreExecutor,
    workspace: RepositoryWorkspace,
    *,
    agent_id: str = "agent-a",
    task_id: str = "task-a",
    idempotency_key: str = "replay-key-v1",
):
    return kernel.invoke(
        agent_id=agent_id,
        task_id=task_id,
        workspace=workspace,
        action=_action(),
        risk_class=ExecutionRisk.R2,
        effect_class=EffectClass.LOCAL_MUTATION,
        required_capabilities=("filesystem",),
        capability_grants=("filesystem",),
        authorization_ref="decision:replay-authority",
        preconditions=(),
        precondition_evidence_refs=(),
        postconditions=("core-outcome-evidenced",),
        postcondition_evidence_refs=(),
        verifier_level=VerifierLevel.V2,
        idempotency_key=idempotency_key,
        recovery_plan="restore isolated workspace checkpoint",
        core_contract_digest="",
        workspace_epoch_id=_epoch(workspace),
        now_ms=100,
        lease_ttl_ms=10_000,
    )


@pytest.mark.parametrize(
    ("agent_id", "task_id"),
    (("agent-b", "task-a"), ("agent-a", "task-b")),
)
def test_idempotency_replay_rejects_cross_authority_reuse(
    tmp_path: Path,
    agent_id: str,
    task_id: str,
) -> None:
    workspace = _workspace(tmp_path)
    raw = _Executor()
    kernel = TransactionalExternalCoreExecutor(executor=raw)
    try:
        first = _invoke(kernel, workspace)
        assert first.record.phase is ActionPhase.COMMITTED
        with pytest.raises(PermissionError, match="replay action authority mismatch"):
            _invoke(kernel, workspace, agent_id=agent_id, task_id=task_id)
        assert raw.calls == 1
    finally:
        workspace.close()


def test_committed_replay_revalidates_concrete_receipt_provenance(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    raw = _Executor()
    kernel = TransactionalExternalCoreExecutor(executor=raw)
    try:
        first = _invoke(kernel, workspace)
        original = raw.get_receipt(first.core_receipt_id)
        raw._receipts[first.core_receipt_id] = replace(original, tool_id="git")

        with pytest.raises(ValueError, match="replay core receipt provenance mismatch"):
            _invoke(kernel, workspace)
        assert raw.calls == 1
    finally:
        workspace.close()


def test_committed_replay_rejects_substituted_output_payload(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    raw = _Executor()
    kernel = TransactionalExternalCoreExecutor(executor=raw)
    try:
        first = _invoke(kernel, workspace)
        original = raw.get_receipt(first.core_receipt_id)
        raw._receipts[first.core_receipt_id] = replace(
            original, output_artifact_ids=("artifact-poisoned",)
        )

        with pytest.raises(ValueError, match="replay core receipt provenance mismatch"):
            _invoke(kernel, workspace)
        assert raw.calls == 1
    finally:
        workspace.close()


def test_noncommitted_terminal_replay_never_exports_core_outputs(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    raw = _Executor()
    protocol = ActingProtocolLedger()
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)
    action = _action()
    epoch_id = _epoch(workspace)
    action_id = kernel._action_id(agent_id="agent-a", task_id="task-a", idempotency_key="replay-key-v1")
    contract = ExecutionContract(
        action_id=action_id,
        core_id=action.tool_id,
        operation=action.operation,
        input_digest=canonical_digest(action.to_state()),
        risk_class=ExecutionRisk.R2,
        effect_class=EffectClass.LOCAL_MUTATION,
        required_capabilities=("filesystem",),
        preconditions=(),
        postconditions=("core-outcome-evidenced",),
        idempotency_key="replay-key-v1",
        recovery_plan="restore isolated workspace checkpoint",
        budget=ActionBudget(
            max_attempts=1,
            max_local_mutations=1,
            max_external_effects=0,
        ),
        core_contract_digest="",
        workspace_epoch_id=epoch_id,
    )
    receipt = _Receipt(
        receipt_id="core-receipt-seeded",
        agent_id="agent-a",
        task_id="task-a",
        tool_id=action.tool_id,
        operation=action.operation,
        input_digest=canonical_digest(action.to_state()),
        authorized=True,
        success=True,
        failure_kind=None,
        before_workspace_digest=workspace.digest,
        after_workspace_digest=workspace.digest,
        output_artifact_ids=("artifact-must-not-replay",),
        evidence_artifact_id="evidence-seeded",
        core_contract_digest="",
        workspace_epoch_id=epoch_id,
    )
    raw._receipts[receipt.receipt_id] = receipt
    protocol.propose(contract)
    protocol.acquire_lease(
        action_id,
        owner_id="agent-a",
        authorization_ref="decision:replay-authority",
        capability_grants=("filesystem",),
        now_ms=100,
        ttl_ms=10_000,
    )
    protocol.verify_preconditions(action_id, evidence_refs=(), now_ms=100)
    protocol.begin_execution(action_id, now_ms=100)
    protocol.observe_outcome(action_id, outcome_ref=receipt.receipt_id, success=True, now_ms=100)
    protocol.rollback(
        action_id,
        rollback_ref="checkpoint:restored",
        failure_reason="forced rollback after observed outcome",
    )

    try:
        replay = _invoke(kernel, workspace)
        assert replay.replayed is True
        assert replay.record.phase is ActionPhase.ROLLED_BACK
        assert replay.core_receipt_id == ""
        assert replay.output_artifact_ids == ()
        assert raw.calls == 0
    finally:
        workspace.close()
