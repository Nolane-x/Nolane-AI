from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.acting_protocol import ActionPhase
from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    OrganizationExecutionControlPlane,
)
from nolane.external_core.execution_types import ExecutionBudget, ExecutionCounters


@dataclass(frozen=True)
class _FakeDecision:
    receipt_id: str


@dataclass(frozen=True)
class _FakeActionRecord:
    action_id: str
    contract: object
    phase: ActionPhase
    terminal_phase: ActionPhase


class _FakeProtocol:
    def __init__(self, rows: tuple[_FakeActionRecord, ...]) -> None:
        self.rows = {row.action_id: row for row in rows}

    def records(self) -> tuple[_FakeActionRecord, ...]:
        return tuple(self.rows[key] for key in sorted(self.rows))


class _FakeActingExecutor:
    def __init__(self, rows: tuple[_FakeActionRecord, ...]) -> None:
        self.protocol = _FakeProtocol(rows)
        self.reconcile_calls = 0
        self.invoke_calls = 0

    def reconcile_inflight(self, *, evidence_ref: str, reason: str) -> tuple[_FakeActionRecord, ...]:
        assert evidence_ref
        assert reason
        self.reconcile_calls += 1
        reconciled: list[_FakeActionRecord] = []
        terminal = {
            ActionPhase.COMMITTED,
            ActionPhase.ROLLED_BACK,
            ActionPhase.DEGRADED,
            ActionPhase.CANCELLED,
        }
        for row in self.protocol.records():
            if row.phase in terminal:
                continue
            updated = replace(row, phase=row.terminal_phase)
            self.protocol.rows[row.action_id] = updated
            reconciled.append(updated)
        return tuple(reconciled)

    def invoke(self, **kwargs):  # pragma: no cover - recovery must never call this path
        self.invoke_calls += 1
        raise AssertionError("restart recovery must not invoke a concrete effect")


class _FakeArtifacts:
    def put(self, *, kind: str, producer_agent_id: str, content: str, evidence_refs=(), metadata=None):
        digest = canonical_digest(
            {
                "kind": kind,
                "producer_agent_id": producer_agent_id,
                "content": content,
                "evidence_refs": list(evidence_refs),
                "metadata": dict(metadata or {}),
            }
        )
        return SimpleNamespace(artifact_id="artifact-" + digest[:24])


def _session(
    session_id: str,
    *,
    decision_ids: tuple[str, ...] = ("decision-1",),
    state: ExecutionState = ExecutionState.RUNNING,
) -> ExecutionSession:
    return ExecutionSession(
        session_id=session_id,
        agent_id="agent-1",
        task_id="task-1",
        action_schema=("filesystem.read_text",),
        budget=ExecutionBudget(
            max_steps=4,
            max_tool_calls=2,
            max_external_core_calls=1,
            max_compute_units=4,
        ),
        counters=ExecutionCounters(steps=len(decision_ids), compute_units=len(decision_ids)),
        step_index=len(decision_ids),
        state=state,
        backend_id="fixture-v1",
        checkpoint_digest="checkpoint-v1",
        workspace_base_revision="base-v1",
        decision_receipt_ids=decision_ids,
    )


def _row(
    action_id: str,
    *,
    session_id: str,
    decision_id: str,
    terminal_phase: ActionPhase,
    phase: ActionPhase = ActionPhase.EXECUTING,
) -> _FakeActionRecord:
    return _FakeActionRecord(
        action_id=action_id,
        contract=SimpleNamespace(idempotency_key=f"{session_id}:{decision_id}"),
        phase=phase,
        terminal_phase=terminal_phase,
    )


def _plane(
    *,
    sessions: tuple[ExecutionSession, ...],
    rows: tuple[_FakeActionRecord, ...],
) -> tuple[OrganizationExecutionControlPlane, _FakeActingExecutor]:
    acting = _FakeActingExecutor(rows)
    decision_ids = sorted({receipt_id for session in sessions for receipt_id in session.decision_receipt_ids})
    plane = OrganizationExecutionControlPlane(
        registry=object(),
        tasks=object(),
        context=object(),
        artifacts=_FakeArtifacts(),
        external_cores=object(),
        coding=object(),
        executor=object(),
        acting_executor=acting,
        sessions=sessions,
        decisions=tuple(_FakeDecision(receipt_id) for receipt_id in decision_ids),
        session_counter=max(int(session.session_id.rsplit("-", 1)[1]) for session in sessions),
    )
    return plane, acting


def test_control_plane_restart_recovery_fails_only_exact_owning_session() -> None:
    owner = _session("execution-00000001")
    unrelated = _session("execution-00000002", decision_ids=("decision-2",))
    plane, acting = _plane(
        sessions=(owner, unrelated),
        rows=(
            _row(
                "acting-action-a",
                session_id=owner.session_id,
                decision_id="decision-1",
                phase=ActionPhase.PRECONDITION_VERIFIED,
                terminal_phase=ActionPhase.CANCELLED,
            ),
        ),
    )

    receipts = plane.reconcile_interrupted_sessions(
        evidence_ref="restart:boot-1",
        reason="runtime restarted before transaction completion",
    )

    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt.session_id == owner.session_id
    assert receipt.state is ExecutionState.FAILED
    assert "acting-action-a" in receipt.termination_reason
    assert "cancelled" in receipt.termination_reason
    assert plane.get_session(owner.session_id).terminal_receipt_id == receipt.receipt_id
    assert plane.get_session(unrelated.session_id).state is ExecutionState.RUNNING
    assert plane.get_session(unrelated.session_id).terminal_receipt_id is None
    assert acting.invoke_calls == 0


def test_control_plane_restart_recovery_does_not_treat_read_rollback_as_session_success() -> None:
    owner = _session("execution-00000001")
    plane, acting = _plane(
        sessions=(owner,),
        rows=(
            _row(
                "acting-action-read",
                session_id=owner.session_id,
                decision_id="decision-1",
                terminal_phase=ActionPhase.ROLLED_BACK,
            ),
        ),
    )

    receipt = plane.reconcile_interrupted_sessions(
        evidence_ref="restart:boot-2",
        reason="runtime interrupted after read dispatch",
    )[0]

    assert receipt.state is ExecutionState.FAILED
    assert "rolled_back" in receipt.termination_reason
    assert plane.get_session(owner.session_id).state is ExecutionState.FAILED
    assert acting.invoke_calls == 0


def test_control_plane_restart_recovery_aggregates_multiple_actions_deterministically() -> None:
    owner = _session("execution-00000001", decision_ids=("decision-1", "decision-2"))
    plane, _ = _plane(
        sessions=(owner,),
        rows=(
            _row(
                "acting-action-z",
                session_id=owner.session_id,
                decision_id="decision-2",
                terminal_phase=ActionPhase.DEGRADED,
            ),
            _row(
                "acting-action-a",
                session_id=owner.session_id,
                decision_id="decision-1",
                terminal_phase=ActionPhase.ROLLED_BACK,
            ),
        ),
    )

    receipts = plane.reconcile_interrupted_sessions(
        evidence_ref="restart:boot-3",
        reason="runtime restarted with uncertain effects",
    )

    assert len(receipts) == 1
    reason = receipts[0].termination_reason
    assert reason.index("acting-action-a") < reason.index("acting-action-z")
    assert "rolled_back" in reason
    assert "degraded" in reason
    assert len(plane.terminal_receipts()) == 1


def test_control_plane_restart_recovery_ignores_unowned_or_mismatched_action_identity() -> None:
    owner = _session("execution-00000001")
    plane, _ = _plane(
        sessions=(owner,),
        rows=(
            _row(
                "acting-action-orphan",
                session_id="execution-99999999",
                decision_id="decision-1",
                terminal_phase=ActionPhase.DEGRADED,
            ),
            _row(
                "acting-action-mismatch",
                session_id=owner.session_id,
                decision_id="decision-not-owned",
                terminal_phase=ActionPhase.CANCELLED,
            ),
        ),
    )

    assert plane.reconcile_interrupted_sessions(
        evidence_ref="restart:boot-4",
        reason="runtime restarted",
    ) == ()
    assert plane.get_session(owner.session_id).state is ExecutionState.RUNNING
    assert plane.get_session(owner.session_id).terminal_receipt_id is None


def test_control_plane_restart_recovery_is_explicit_and_idempotent() -> None:
    owner = _session("execution-00000001")
    plane, acting = _plane(
        sessions=(owner,),
        rows=(
            _row(
                "acting-action-a",
                session_id=owner.session_id,
                decision_id="decision-1",
                terminal_phase=ActionPhase.DEGRADED,
            ),
        ),
    )

    first = plane.reconcile_interrupted_sessions(
        evidence_ref="restart:boot-5",
        reason="runtime restarted",
    )
    second = plane.reconcile_interrupted_sessions(
        evidence_ref="restart:boot-5",
        reason="runtime restarted",
    )

    assert len(first) == 1
    assert second == ()
    assert len(plane.terminal_receipts()) == 1
    assert acting.reconcile_calls == 2
    assert acting.invoke_calls == 0
