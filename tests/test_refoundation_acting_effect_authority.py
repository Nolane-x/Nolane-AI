from __future__ import annotations

from dataclasses import dataclass

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import (
    ActionBudget,
    ActingProtocolLedger,
    EffectClass,
    ExecutionContract,
    ExecutionRisk,
    VerifierLevel,
)
from nolane.external_core.acting_runtime import TransactionalExternalCoreExecutor
from nolane.external_core.execution_types import ToolAction


@dataclass
class _Workspace:
    digest: str = "workspace-before"


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


class _RecordingExecutor:
    def __init__(self) -> None:
        self.calls = 0
        self._receipts: dict[str, _Receipt] = {}

    def invoke(self, *, agent_id: str, task_id: str, workspace: _Workspace, action: ToolAction, **_: object) -> _Receipt:
        self.calls += 1
        before = workspace.digest
        if action.mutation_paths:
            workspace.digest = "workspace-after-mutation"
        receipt = _Receipt(
            receipt_id=f"receipt-{self.calls}",
            agent_id=agent_id,
            task_id=task_id,
            tool_id=action.tool_id,
            operation=action.operation,
            input_digest=canonical_digest(action.to_state()),
            authorized=True,
            success=True,
            failure_kind=None,
            before_workspace_digest=before,
            after_workspace_digest=workspace.digest,
            output_artifact_ids=(),
            evidence_artifact_id=f"evidence-{self.calls}",
        )
        self._receipts[receipt.receipt_id] = receipt
        return receipt

    def get_receipt(self, receipt_id: str) -> _Receipt:
        return self._receipts[receipt_id]


def _contract(*, risk: ExecutionRisk, effect: EffectClass) -> ExecutionContract:
    return ExecutionContract(
        action_id=f"action-{risk.value}-{effect.value}",
        core_id="core",
        operation="operate",
        input_digest="input-digest",
        risk_class=risk,
        effect_class=effect,
        required_capabilities=("core",),
        preconditions=(),
        postconditions=(),
        idempotency_key=f"idem-{risk.value}-{effect.value}",
        recovery_plan="operator recovery" if effect is EffectClass.IRREVERSIBLE else "",
        budget=ActionBudget(max_attempts=1, max_local_mutations=1, max_external_effects=1),
    )


@pytest.mark.parametrize(
    ("risk", "effect"),
    (
        (ExecutionRisk.R0, EffectClass.READ),
        (ExecutionRisk.R1, EffectClass.LOCAL_MUTATION),
        (ExecutionRisk.R2, EffectClass.EXTERNAL_MUTATION),
        (ExecutionRisk.R3, EffectClass.IRREVERSIBLE),
    ),
)
def test_execution_contract_rejects_risk_below_effect_authority_floor(
    risk: ExecutionRisk,
    effect: EffectClass,
) -> None:
    with pytest.raises(ValueError, match="risk class understates effect class"):
        _contract(risk=risk, effect=effect)


@pytest.mark.parametrize(
    "action",
    (
        ToolAction.from_arguments(
            "filesystem",
            "write_text",
            {"path": "README.md", "content": "mutated\n"},
        ),
        ToolAction.from_arguments("terminal", "run", {"argv": ["python", "-V"]}),
        ToolAction.from_arguments("custom-handler", "invoke", {"value": 1}),
    ),
)
def test_transactional_runtime_rejects_physical_effect_downgrade_before_dispatch(action: ToolAction) -> None:
    workspace = _Workspace()
    raw = _RecordingExecutor()
    protocol = ActingProtocolLedger()
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)

    with pytest.raises(PermissionError, match="effect classification downgrade"):
        kernel.invoke(
            agent_id="agent-1",
            task_id="task-1",
            workspace=workspace,  # type: ignore[arg-type]
            action=action,
            risk_class=ExecutionRisk.R1,
            effect_class=EffectClass.READ,
            required_capabilities=(action.tool_id,),
            capability_grants=(action.tool_id,),
            authorization_ref="decision:1",
            preconditions=(),
            precondition_evidence_refs=(),
            postconditions=("core-outcome-evidenced",),
            postcondition_evidence_refs=(),
            verifier_level=VerifierLevel.V1,
            idempotency_key=f"task-1:{action.tool_id}:{action.operation}",
            now_ms=100,
            lease_ttl_ms=10_000,
        )

    assert raw.calls == 0
    assert protocol.records() == ()
    assert workspace.digest == "workspace-before"


def test_transactional_runtime_accepts_canonical_bounded_read_floor() -> None:
    action = ToolAction.from_arguments("filesystem", "read_text", {"path": "README.md"})
    workspace = _Workspace()
    raw = _RecordingExecutor()
    protocol = ActingProtocolLedger()
    kernel = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)

    result = kernel.invoke(
        agent_id="agent-1",
        task_id="task-1",
        workspace=workspace,  # type: ignore[arg-type]
        action=action,
        risk_class=ExecutionRisk.R1,
        effect_class=EffectClass.READ,
        required_capabilities=("filesystem",),
        capability_grants=("filesystem",),
        authorization_ref="decision:read",
        preconditions=(),
        precondition_evidence_refs=(),
        postconditions=("core-outcome-evidenced",),
        postcondition_evidence_refs=(),
        verifier_level=VerifierLevel.V1,
        idempotency_key="task-1:filesystem:read",
        now_ms=100,
        lease_ttl_ms=10_000,
    )

    assert result.record.phase.value == "committed"
    assert raw.calls == 1
