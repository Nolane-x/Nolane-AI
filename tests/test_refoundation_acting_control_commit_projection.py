from __future__ import annotations

from dataclasses import dataclass

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
from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    ExecutionStepReceipt,
    OrganizationExecutionControlPlane,
)
from nolane.external_core.execution_types import (
    ExecutionAction,
    ExecutionBudget,
    ExecutionCounters,
    ToolAction,
)


_TOOL_ACTION = ToolAction.from_arguments(
    "filesystem",
    "write_text",
    {"path": "README.md", "content": "changed\n"},
)
_ACTION_SCHEMA = ("filesystem.write_text",)
_ACTION_SCHEMA_DIGEST = canonical_digest(list(_ACTION_SCHEMA))
_TOOL_INPUT_DIGEST = canonical_digest(_TOOL_ACTION.to_state())


@dataclass(frozen=True)
class _Decision:
    receipt_id: str
    agent_id: str = "agent-1"
    backend_id: str = "backend-v1"
    checkpoint_digest: str = "checkpoint-v1"
    action_schema_digest: str = _ACTION_SCHEMA_DIGEST
    step_index: int = 0
    action: ExecutionAction = ExecutionAction.tool(_TOOL_ACTION)


@dataclass(frozen=True)
class _CoreReceipt:
    receipt_id: str
    agent_id: str = "agent-1"
    task_id: str = "task-1"
    tool_id: str = "filesystem"
    operation: str = "write_text"
    input_digest: str = _TOOL_INPUT_DIGEST
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
        raise AssertionError("commit projection must never re-invoke a side effect")

    def get_receipt(self, receipt_id: str) -> _CoreReceipt:
        self.get_calls += 1
        if receipt_id != self.receipt.receipt_id:
            raise KeyError(receipt_id)
        return self.receipt


class _Artifacts:
    def put(self, **_: object):
        raise AssertionError("known committed projection must not create terminal evidence")


class _NeverUse:
    def __getattr__(self, name: str):
        raise AssertionError(f"commit projection must not use {name}")


def _session() -> ExecutionSession:
    return ExecutionSession(
        session_id="execution-00000001",
        agent_id="agent-1",
        task_id="task-1",
        action_schema=_ACTION_SCHEMA,
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
        input_digest=_TOOL_INPUT_DIGEST,
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


def test_control_plane_projects_known_committed_acting_result_without_reinvocation() -> None:
    protocol = _committed_protocol()
    core = _CoreReceipt(receipt_id="core-1")
    executor = _Executor(core)
    acting = TransactionalExternalCoreExecutor(executor=executor, protocol=protocol)
    plane = OrganizationExecutionControlPlane(
        registry=_NeverUse(),
        tasks=_NeverUse(),
        context=_NeverUse(),
        artifacts=_Artifacts(),
        external_cores=_NeverUse(),
        coding=_NeverUse(),
        encoder=_NeverUse(),
        executor=executor,
        acting_executor=acting,
        sessions=(_session(),),
        decisions=(_Decision(receipt_id="decision-1"),),
        session_counter=1,
    )

    projected = plane.reconcile_interrupted_sessions(
        evidence_ref="recovery:restart-after-commit",
        reason="restart after acting commit before session projection",
    )

    assert len(projected) == 1
    assert isinstance(projected[0], ExecutionStepReceipt)
    session = plane.get_session("execution-00000001")
    assert session.state is ExecutionState.RUNNING
    assert session.terminal_receipt_id is None
    assert session.counters.tool_calls == 1
    assert session.core_receipt_ids == ("core-1",)
    assert session.output_artifact_ids == ("artifact-1",)
    assert session.step_receipt_ids == (projected[0].receipt_id,)
    assert session.current_workspace_digest == "workspace-after"
    assert projected[0].decision_receipt_id == "decision-1"
    assert projected[0].core_receipt_id == "core-1"
    assert projected[0].before_workspace_digest == "workspace-before"
    assert projected[0].after_workspace_digest == "workspace-after"
    assert executor.invoke_calls == 0
    assert executor.get_calls == 1

    assert plane.reconcile_interrupted_sessions(
        evidence_ref="recovery:restart-repeat",
        reason="repeat projection is a no-op",
    ) == ()
    assert executor.invoke_calls == 0
    assert executor.get_calls == 1
