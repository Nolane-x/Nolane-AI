from __future__ import annotations

from dataclasses import dataclass, replace

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
from nolane.external_core.execution import ExecutionSession, ExecutionState, OrganizationExecutionControlPlane
from nolane.external_core.execution_types import ExecutionAction, ExecutionBudget, ExecutionCounters, ToolAction


_TOOL_ACTION = ToolAction.from_arguments(
    "filesystem",
    "write_text",
    {"path": "README.md", "content": "changed\n"},
)
_SCHEMA = ("filesystem.write_text",)
_SCHEMA_DIGEST = canonical_digest(list(_SCHEMA))
_INPUT_DIGEST = canonical_digest(_TOOL_ACTION.to_state())


@dataclass(frozen=True)
class _Decision:
    receipt_id: str = "decision-1"
    agent_id: str = "agent-1"
    backend_id: str = "backend-v1"
    checkpoint_digest: str = "checkpoint-v1"
    action_schema_digest: str = _SCHEMA_DIGEST
    step_index: int = 0
    action: ExecutionAction = ExecutionAction.tool(_TOOL_ACTION)


@dataclass(frozen=True)
class _CoreReceipt:
    receipt_id: str = "core-1"
    agent_id: str = "agent-1"
    task_id: str = "task-1"
    tool_id: str = "filesystem"
    operation: str = "write_text"
    input_digest: str = _INPUT_DIGEST
    authorized: bool = True
    success: bool = True
    failure_kind: str | None = None
    output_artifact_ids: tuple[str, ...] = ("artifact-1",)
    evidence_artifact_id: str = "evidence-core-1"
    before_workspace_digest: str = "workspace-before"
    after_workspace_digest: str = "workspace-after"


class _Executor:
    external_core_ids = frozenset()

    def __init__(self, receipt: _CoreReceipt) -> None:
        self.receipt = receipt
        self.invoke_calls = 0
        self.get_calls = 0

    def invoke(self, **_: object):
        self.invoke_calls += 1
        raise AssertionError("recovery projection must never re-invoke an effect")

    def get_receipt(self, _receipt_id: str) -> _CoreReceipt:
        self.get_calls += 1
        return self.receipt


class _Artifacts:
    def __init__(self) -> None:
        self.calls = 0

    def put(self, **_: object):
        self.calls += 1
        raise AssertionError("authority rejection must not issue recovery artifacts")


class _NeverUse:
    def __getattr__(self, name: str):
        raise AssertionError(f"recovery authority test must not use {name}")


def _session() -> ExecutionSession:
    return ExecutionSession(
        session_id="execution-00000001",
        agent_id="agent-1",
        task_id="task-1",
        action_schema=_SCHEMA,
        budget=ExecutionBudget(
            max_steps=4,
            max_tool_calls=2,
            max_external_core_calls=1,
            max_compute_units=4,
        ),
        counters=ExecutionCounters(steps=1, compute_units=1),
        step_index=1,
        state=ExecutionState.RUNNING,
        backend_id="backend-v1",
        checkpoint_digest="checkpoint-v1",
        workspace_base_revision="base-v1",
        workspace_provenance_version=2,
        initial_workspace_digest="workspace-before",
        current_workspace_digest="workspace-before",
        decision_receipt_ids=("decision-1",),
    )


def _committed_protocol() -> ActingProtocolLedger:
    protocol = ActingProtocolLedger()
    contract = ExecutionContract(
        action_id="action-committed",
        core_id="filesystem",
        operation="write_text",
        input_digest=_INPUT_DIGEST,
        risk_class=ExecutionRisk.R2,
        effect_class=EffectClass.LOCAL_MUTATION,
        required_capabilities=("filesystem",),
        preconditions=("authorized",),
        postconditions=("evidenced",),
        idempotency_key="execution-00000001:decision-1",
        recovery_plan="",
        budget=ActionBudget(max_attempts=1, max_local_mutations=1, max_external_effects=0),
    )
    protocol.propose(contract)
    protocol.acquire_lease(
        contract.action_id,
        owner_id="agent-1",
        authorization_ref="decision:decision-1",
        capability_grants=("filesystem",),
        now_ms=100,
        ttl_ms=10_000,
    )
    protocol.verify_preconditions(contract.action_id, evidence_refs=("evidence:pre",), now_ms=101)
    protocol.begin_execution(contract.action_id, now_ms=102)
    protocol.observe_outcome(contract.action_id, outcome_ref="core-1", success=True, now_ms=103)
    protocol.verify_postconditions(
        contract.action_id,
        evidence_refs=("evidence-core-1",),
        verifier_level=VerifierLevel.V2,
        now_ms=104,
    )
    protocol.commit(contract.action_id, commit_ref="core-1", now_ms=105)
    return protocol


def _plane(receipt: _CoreReceipt):
    protocol = _committed_protocol()
    executor = _Executor(receipt)
    artifacts = _Artifacts()
    plane = OrganizationExecutionControlPlane(
        registry=_NeverUse(),
        tasks=_NeverUse(),
        context=_NeverUse(),
        artifacts=artifacts,
        external_cores=_NeverUse(),
        coding=_NeverUse(),
        encoder=_NeverUse(),
        executor=executor,
        acting_executor=TransactionalExternalCoreExecutor(executor=executor, protocol=protocol),
        sessions=(_session(),),
        decisions=(_Decision(),),
        session_counter=1,
    )
    return plane, protocol, executor, artifacts


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("receipt_id", "core-substituted"),
        ("agent_id", "agent-2"),
        ("task_id", "task-2"),
        ("tool_id", "git"),
        ("operation", "status"),
        ("input_digest", "substituted-input"),
        ("authorized", False),
        ("after_workspace_digest", "workspace-poisoned"),
        ("output_artifact_ids", ("artifact-poisoned",)),
    ),
)
def test_committed_recovery_rejects_substituted_core_authority_before_projection(
    field: str,
    value: object,
) -> None:
    receipt = replace(_CoreReceipt(), **{field: value})
    plane, protocol, executor, artifacts = _plane(receipt)
    before_session = plane.get_session("execution-00000001")
    before_protocol = protocol.to_state()

    with pytest.raises(ValueError, match="committed acting core receipt authority mismatch"):
        plane.reconcile_interrupted_sessions(
            evidence_ref="recovery:restart-authority-test",
            reason="restart after commit before projection",
        )

    assert plane.get_session("execution-00000001") == before_session
    assert protocol.to_state() == before_protocol
    assert executor.invoke_calls == 0
    assert executor.get_calls == 1
    assert artifacts.calls == 0


def test_valid_committed_recovery_receipt_still_projects_without_reinvocation() -> None:
    plane, protocol, executor, artifacts = _plane(_CoreReceipt())

    projected = plane.reconcile_interrupted_sessions(
        evidence_ref="recovery:restart-valid",
        reason="restart after commit before projection",
    )

    assert len(projected) == 1
    assert plane.get_session("execution-00000001").core_receipt_ids == ("core-1",)
    assert protocol.get("action-committed").commit_ref == "core-1"
    assert executor.invoke_calls == 0
    assert executor.get_calls == 1
    assert artifacts.calls == 0
