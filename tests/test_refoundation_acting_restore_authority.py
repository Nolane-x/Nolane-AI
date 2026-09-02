from __future__ import annotations

from dataclasses import replace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    ExecutionStepReceipt,
    ExecutionTerminalReceipt,
    OrganizationExecutionControlPlane,
)
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionBudget,
    ExecutionCounters,
    InferenceRequest,
)


_SCHEMA = ("control.wait",)
_SCHEMA_DIGEST = canonical_digest(list(_SCHEMA))


class _NeverUse:
    def __getattr__(self, name: str):
        raise AssertionError(f"restore authority test must not use {name}")


def _session(**changes: object) -> ExecutionSession:
    row = ExecutionSession(
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
        counters=ExecutionCounters(),
        step_index=0,
        state=ExecutionState.RUNNING,
        backend_id="backend-v1",
        checkpoint_digest="checkpoint-v1",
        workspace_base_revision="base-v1",
    )
    return replace(row, **changes)


def _decision() -> AgentDecisionReceipt:
    request = InferenceRequest(
        agent_id="agent-1",
        neural_version="neural-v1",
        task_id="task-1",
        context_digest="context-v1",
        encoder_version="encoder-v1",
        checkpoint_digest="checkpoint-v1",
        action_schema=_SCHEMA,
        action_schema_digest=_SCHEMA_DIGEST,
        counters=ExecutionCounters(),
        step_index=0,
    )
    return AgentDecisionReceipt.create(
        backend_id="backend-v1",
        request=request,
        action=ExecutionAction.wait(reason="restore authority fixture"),
    )


def _step() -> ExecutionStepReceipt:
    return ExecutionStepReceipt.create(
        session_id="execution-00000001",
        step_index=0,
        decision_receipt_id=_decision().receipt_id,
        core_receipt_id=None,
        before_workspace_digest="workspace-v1",
        after_workspace_digest="workspace-v1",
        state_after=ExecutionState.WAITING,
    )


def _terminal() -> ExecutionTerminalReceipt:
    row = ExecutionTerminalReceipt(
        receipt_id="",
        session_id="execution-00000001",
        agent_id="agent-1",
        task_id="task-1",
        state=ExecutionState.ABORTED,
        termination_reason="restore authority fixture",
        steps=0,
        tool_calls=0,
        external_core_calls=0,
        compute_units=0,
        wall_clock_ms=0,
        decision_receipt_ids=(),
        step_receipt_ids=(),
        core_receipt_ids=(),
        output_artifact_ids=(),
        digest="",
    )
    digest = canonical_digest(row.payload())
    return replace(row, receipt_id="terminal-" + digest[:24], digest=digest)


def _plane(
    *,
    sessions: tuple[ExecutionSession, ...] = (),
    decisions: tuple[AgentDecisionReceipt, ...] = (),
    steps: tuple[ExecutionStepReceipt, ...] = (),
    terminals: tuple[ExecutionTerminalReceipt, ...] = (),
) -> OrganizationExecutionControlPlane:
    never = _NeverUse()
    return OrganizationExecutionControlPlane(
        registry=never,
        tasks=never,
        context=never,
        artifacts=never,
        external_cores=never,
        coding=never,
        encoder=never,
        executor=never,
        acting_executor=never,
        sessions=sessions,
        decisions=decisions,
        steps=steps,
        terminals=terminals,
        session_counter=1 if sessions else 0,
    )


@pytest.mark.parametrize("authority_kind", ("decision", "step", "terminal"))
def test_restore_rejects_integrity_valid_but_unowned_authority(authority_kind: str) -> None:
    kwargs: dict[str, object] = {"sessions": (_session(),)}
    if authority_kind == "decision":
        decision = _decision()
        assert AgentDecisionReceipt.from_state(decision.to_state()) == decision
        kwargs["decisions"] = (decision,)
    elif authority_kind == "step":
        step = _step()
        assert ExecutionStepReceipt.from_state(step.to_state()) == step
        kwargs["steps"] = (step,)
    else:
        terminal = _terminal()
        assert ExecutionTerminalReceipt.from_state(terminal.to_state()) == terminal
        kwargs["terminals"] = (terminal,)

    with pytest.raises(ValueError, match="unowned .* receipt"):
        _plane(**kwargs)


def test_restore_rejects_core_authority_without_step_projection() -> None:
    poisoned = _session(core_receipt_ids=("core-unproven",))

    with pytest.raises(ValueError, match="core receipt projection mismatch"):
        _plane(sessions=(poisoned,))


@pytest.mark.parametrize("authority_kind", ("session", "decision", "step", "terminal"))
def test_restore_rejects_duplicate_serialized_authority_ids_before_dict_collapse(
    authority_kind: str,
) -> None:
    kwargs: dict[str, object] = {}
    if authority_kind == "session":
        row = _session()
        kwargs["sessions"] = (row, row)
    elif authority_kind == "decision":
        row = _decision()
        kwargs["decisions"] = (row, row)
    elif authority_kind == "step":
        row = _step()
        kwargs["steps"] = (row, row)
    else:
        row = _terminal()
        kwargs["terminals"] = (row, row)

    with pytest.raises(ValueError, match=f"duplicate execution {authority_kind} .*id"):
        _plane(**kwargs)
