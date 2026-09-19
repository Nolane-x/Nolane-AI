import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution_types import (
    ExecutionBudget,
    ExecutionCounters,
    InferenceRequest,
)


_BUDGET_FIELDS = (
    "max_steps",
    "max_tool_calls",
    "max_external_core_calls",
    "max_compute_units",
)

_COUNTER_FIELDS = (
    "steps",
    "tool_calls",
    "external_core_calls",
    "compute_units",
)

_INTEGER_ALIASES = (True, 1.0, "1")


def _request() -> InferenceRequest:
    schema = ("inspect", "complete")
    return InferenceRequest(
        agent_id="agent-r262",
        neural_version="Neural-R2.3-Ultra-Recursive-DAgger-Gated",
        task_id="task-r262",
        context_digest=canonical_digest({"context": "r262"}),
        encoder_version="encoder-r262",
        checkpoint_digest="checkpoint-r262",
        action_schema=schema,
        action_schema_digest=canonical_digest(list(schema)),
        counters=ExecutionCounters(
            steps=1,
            tool_calls=1,
            external_core_calls=1,
            compute_units=1,
        ),
        step_index=1,
        execution_lineage_version=1,
    )


@pytest.mark.parametrize("field", _BUDGET_FIELDS)
@pytest.mark.parametrize("alias", _INTEGER_ALIASES)
def test_r262_budget_restore_rejects_non_exact_integer_authority(
    field: str,
    alias: object,
) -> None:
    canonical = ExecutionBudget(1, 1, 1, 1)
    state = canonical.to_state()
    state[field] = alias

    with pytest.raises(ValueError, match="execution budgets must be positive integers"):
        ExecutionBudget.from_state(state)


@pytest.mark.parametrize("field", _COUNTER_FIELDS)
@pytest.mark.parametrize("alias", _INTEGER_ALIASES)
def test_r262_counter_restore_rejects_non_exact_integer_authority(
    field: str,
    alias: object,
) -> None:
    canonical = ExecutionCounters(
        steps=1,
        tool_calls=1,
        external_core_calls=1,
        compute_units=1,
    )
    state = canonical.to_state()
    state[field] = alias

    with pytest.raises(ValueError, match="execution counters must be non-negative integers"):
        ExecutionCounters.from_state(state)


@pytest.mark.parametrize("field", _COUNTER_FIELDS)
@pytest.mark.parametrize("alias", _INTEGER_ALIASES)
def test_r262_inference_request_restore_rejects_laundered_counter_authority(
    field: str,
    alias: object,
) -> None:
    canonical = _request()
    state = canonical.to_state()
    state["counters"][field] = alias

    with pytest.raises(ValueError, match="execution counters must be non-negative integers"):
        InferenceRequest.from_state(state)


def test_r262_exact_integer_execution_scalars_roundtrip_without_semantic_change() -> None:
    budget = ExecutionBudget(5, 4, 3, 2)
    counters = ExecutionCounters(
        steps=4,
        tool_calls=3,
        external_core_calls=2,
        compute_units=1,
    )
    request = _request()

    restored_budget = ExecutionBudget.from_state(budget.to_state())
    restored_counters = ExecutionCounters.from_state(counters.to_state())
    restored_request = InferenceRequest.from_state(request.to_state())

    assert restored_budget == budget
    assert restored_counters == counters
    assert restored_request == request
    assert all(type(getattr(restored_budget, field)) is int for field in _BUDGET_FIELDS)
    assert all(type(getattr(restored_counters, field)) is int for field in _COUNTER_FIELDS)
    assert all(type(getattr(restored_request.counters, field)) is int for field in _COUNTER_FIELDS)
