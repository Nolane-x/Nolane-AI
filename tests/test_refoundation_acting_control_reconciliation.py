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
)
from nolane.external_core.acting_runtime import TransactionalExternalCoreExecutor
from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    OrganizationExecutionControlPlane,
)
from nolane.external_core.execution_types import (
    ExecutionAction,
    ExecutionBudget,
    ExecutionCounters,
    ToolAction,
)


@dataclass(frozen=True)
class _Artifact:
    artifact_id: str


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


class _Artifacts:
    def __init__(self) -> None:
        self.calls = 0

    def put(self, **_: object) -> _Artifact:
        self.calls += 1
        return _Artifact(artifact_id=f"recovery-evidence-{self.calls}")


class _NeverInvokeExecutor:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, **_: object):
        self.calls += 1
        raise AssertionError("control-plane recovery must never execute a side effect")

    def get_receipt(self, receipt_id: str):
        raise KeyError(receipt_id)


class _NeverInference:
    def __getattr__(self, name: str):
        raise AssertionError(f"control-plane recovery must not use inference surface: {name}")


def _session(
    session_id: str,
    *,
    state: ExecutionState = ExecutionState.RUNNING,
    decision_ids: tuple[str, ...] = (),
) -> ExecutionSession:
    return ExecutionSession(
        session_id=session_id,
        agent_id="agent-1",
        task_id=f"task-{session_id[-1]}",
        action_schema=_ACTION_SCHEMA,
        budget=ExecutionBudget(
            max_steps=4,
            max_tool_calls=2,
            max_external_core_calls=1,
            max_compute_units=4,
        ),
        counters=ExecutionCounters(
            steps=len(decision_ids),
            compute_units=len(decision_ids),
        ),
        step_index=len(decision_ids),
        state=state,
        backend_id="backend-v1",
        checkpoint_digest="checkpoint-v1",
        workspace_base_revision="base-v1",
        decision_receipt_ids=decision_ids,
    )


def _prepare_interrupted(
    protocol: ActingProtocolLedger,
    *,
    session_id: str,
    decision_id: str,
    effect: EffectClass,
    begin_execution: bool,
) -> None:
    risk = {
        EffectClass.READ: ExecutionRisk.R1,
        EffectClass.LOCAL_MUTATION: ExecutionRisk.R2,
        EffectClass.EXTERNAL_MUTATION: ExecutionRisk.R3,
        EffectClass.IRREVERSIBLE: ExecutionRisk.R4,
    }[effect]
    contract = ExecutionContract(
        action_id=f"action-{session_id}",
        core_id="filesystem",
        operation="write_text",
        input_digest=_TOOL_INPUT_DIGEST,
        risk_class=risk,
        effect_class=effect,
        required_capabilities=("filesystem",),
        preconditions=("authorized",),
        postconditions=("evidenced",),
        idempotency_key=f"{session_id}:{decision_id}",
        recovery_plan="operator recovery" if effect is EffectClass.IRREVERSIBLE else "",
        budget=ActionBudget(
            max_attempts=1,
            max_local_mutations=1 if effect is EffectClass.LOCAL_MUTATION else 0,
            max_external_effects=1 if effect in {EffectClass.EXTERNAL_MUTATION, EffectClass.IRREVERSIBLE} else 0,
        ),
    )
    protocol.propose(contract)
    protocol.acquire_lease(
        contract.action_id,
        owner_id="agent-1",
        authorization_ref=f"decision:{decision_id}",
        capability_grants=("filesystem",),
        now_ms=100,
        ttl_ms=10_000,
    )
    protocol.verify_preconditions(contract.action_id, evidence_refs=("evidence:pre",), now_ms=101)
    if begin_execution:
        protocol.begin_execution(contract.action_id, now_ms=102)


def _control_plane(
    *,
    sessions: tuple[ExecutionSession, ...],
    protocol: ActingProtocolLedger,
) -> tuple[OrganizationExecutionControlPlane, _NeverInvokeExecutor, _Artifacts]:
    raw = _NeverInvokeExecutor()
    acting = TransactionalExternalCoreExecutor(executor=raw, protocol=protocol)
    artifacts = _Artifacts()
    decisions = tuple(
        _Decision(receipt_id=receipt_id)
        for session in sessions
        for receipt_id in session.decision_receipt_ids
    )
    plane = OrganizationExecutionControlPlane(
        registry=_NeverInference(),
        tasks=_NeverInference(),
        context=_NeverInference(),
        artifacts=artifacts,
        external_cores=_NeverInference(),
        coding=_NeverInference(),
        encoder=_NeverInference(),
        executor=raw,
        acting_executor=acting,
        sessions=sessions,
        decisions=decisions,
        session_counter=max(int(row.session_id.rsplit("-", 1)[1]) for row in sessions),
    )
    return plane, raw, artifacts


def test_control_plane_recovery_terminalizes_only_session_owning_interrupted_action() -> None:
    protocol = ActingProtocolLedger()
    _prepare_interrupted(
        protocol,
        session_id="execution-00000001",
        decision_id="decision-1",
        effect=EffectClass.EXTERNAL_MUTATION,
        begin_execution=True,
    )
    plane, raw, artifacts = _control_plane(
        sessions=(
            _session("execution-00000001", decision_ids=("decision-1",)),
            _session("execution-00000002"),
        ),
        protocol=protocol,
    )

    receipts = plane.reconcile_interrupted_sessions(
        evidence_ref="recovery:restart-1",
        reason="process restarted with an in-flight effect",
    )

    assert len(receipts) == 1
    recovered = plane.get_session("execution-00000001")
    unrelated = plane.get_session("execution-00000002")
    assert recovered.state is ExecutionState.FAILED
    assert recovered.terminal_receipt_id == receipts[0].receipt_id
    assert unrelated.state is ExecutionState.RUNNING
    assert unrelated.terminal_receipt_id is None
    assert "acting-action=" in receipts[0].termination_reason
    assert "phase=degraded" in receipts[0].termination_reason
    assert raw.calls == 0
    assert artifacts.calls == 1


def test_control_plane_recovery_is_idempotent_and_never_runs_inference_or_tools() -> None:
    protocol = ActingProtocolLedger()
    _prepare_interrupted(
        protocol,
        session_id="execution-00000001",
        decision_id="decision-1",
        effect=EffectClass.LOCAL_MUTATION,
        begin_execution=False,
    )
    plane, raw, artifacts = _control_plane(
        sessions=(_session("execution-00000001", decision_ids=("decision-1",)),),
        protocol=protocol,
    )

    first = plane.reconcile_interrupted_sessions(
        evidence_ref="recovery:restart-1",
        reason="restart before effect dispatch",
    )
    second = plane.reconcile_interrupted_sessions(
        evidence_ref="recovery:restart-2",
        reason="repeat recovery",
    )

    assert len(first) == 1
    assert second == ()
    assert plane.get_session("execution-00000001").state is ExecutionState.ABORTED
    assert raw.calls == 0
    assert artifacts.calls == 1


def test_control_plane_preflights_all_inflight_ownership_before_mutating_acting_ledger() -> None:
    protocol = ActingProtocolLedger()
    _prepare_interrupted(
        protocol,
        session_id="execution-00000001",
        decision_id="decision-1",
        effect=EffectClass.EXTERNAL_MUTATION,
        begin_execution=True,
    )
    _prepare_interrupted(
        protocol,
        session_id="execution-00000999",
        decision_id="decision-orphan",
        effect=EffectClass.EXTERNAL_MUTATION,
        begin_execution=True,
    )
    plane, raw, artifacts = _control_plane(
        sessions=(_session("execution-00000001", decision_ids=("decision-1",)),),
        protocol=protocol,
    )
    before = protocol.to_state()

    with pytest.raises(ValueError, match="interrupted action has no owning execution session"):
        plane.reconcile_interrupted_sessions(
            evidence_ref="recovery:restart-1",
            reason="restart with orphan transaction",
        )

    assert protocol.to_state() == before
    assert plane.get_session("execution-00000001").state is ExecutionState.RUNNING
    assert raw.calls == 0
    assert artifacts.calls == 0


def test_control_plane_preflight_rejects_decision_binding_mismatch_without_mutation() -> None:
    protocol = ActingProtocolLedger()
    _prepare_interrupted(
        protocol,
        session_id="execution-00000001",
        decision_id="decision-wrong",
        effect=EffectClass.EXTERNAL_MUTATION,
        begin_execution=True,
    )
    plane, raw, artifacts = _control_plane(
        sessions=(_session("execution-00000001", decision_ids=("decision-1",)),),
        protocol=protocol,
    )
    before = protocol.to_state()

    with pytest.raises(ValueError, match="interrupted action decision is not owned by execution session"):
        plane.reconcile_interrupted_sessions(
            evidence_ref="recovery:restart-1",
            reason="restart with mismatched decision binding",
        )

    assert protocol.to_state() == before
    assert raw.calls == 0
    assert artifacts.calls == 0


def test_control_plane_rejects_interrupted_action_bound_to_non_running_session() -> None:
    protocol = ActingProtocolLedger()
    _prepare_interrupted(
        protocol,
        session_id="execution-00000001",
        decision_id="decision-1",
        effect=EffectClass.EXTERNAL_MUTATION,
        begin_execution=True,
    )
    plane, raw, artifacts = _control_plane(
        sessions=(
            _session(
                "execution-00000001",
                state=ExecutionState.COMPLETED,
                decision_ids=("decision-1",),
            ),
        ),
        protocol=protocol,
    )
    before = protocol.to_state()

    with pytest.raises(ValueError, match="interrupted action belongs to non-running execution session"):
        plane.reconcile_interrupted_sessions(
            evidence_ref="recovery:restart-1",
            reason="restart after inconsistent session persistence",
        )

    assert protocol.to_state() == before
    assert raw.calls == 0
    assert artifacts.calls == 0
