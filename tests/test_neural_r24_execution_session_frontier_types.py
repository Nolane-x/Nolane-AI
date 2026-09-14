import pytest

from nolane.external_core.execution import ExecutionSession, ExecutionState
from nolane.external_core.execution_types import ExecutionBudget, ExecutionCounters


_NON_INTEGER_FRONTIER_ALIASES = (False, 0.0, '0')


def _session(*, step_index: object = 0) -> ExecutionSession:
    return ExecutionSession(
        session_id='execution-00000001',
        agent_id='agent-1',
        task_id='task-1',
        action_schema=('complete',),
        budget=ExecutionBudget(
            max_steps=4,
            max_tool_calls=2,
            max_external_core_calls=1,
            max_compute_units=4,
        ),
        counters=ExecutionCounters(),
        step_index=step_index,  # type: ignore[arg-type]
        state=ExecutionState.RUNNING,
        backend_id='fixture-v1',
        checkpoint_digest='checkpoint-v1',
        workspace_base_revision='base-v1',
    )


@pytest.mark.parametrize('step_index', _NON_INTEGER_FRONTIER_ALIASES)
def test_direct_execution_session_rejects_non_integer_frontier_alias(step_index: object) -> None:
    with pytest.raises(
        ValueError,
        match='execution session step index must be a non-negative integer',
    ):
        _session(step_index=step_index)


@pytest.mark.parametrize('step_index', _NON_INTEGER_FRONTIER_ALIASES)
def test_execution_session_restore_rejects_non_integer_frontier_alias(step_index: object) -> None:
    state = _session().to_state()
    state['step_index'] = step_index

    with pytest.raises(
        ValueError,
        match='execution session step index must be a non-negative integer',
    ):
        ExecutionSession.from_state(state)


def test_execution_session_exact_integer_frontier_round_trip_is_stable() -> None:
    session = _session(step_index=0)

    assert type(session.step_index) is int
    assert ExecutionSession.from_state(session.to_state()) == session
