import pytest

from nolane.external_core.execution_types import ExecutionBudget, ExecutionCounters


def _budget() -> ExecutionBudget:
    return ExecutionBudget(
        max_steps=8,
        max_tool_calls=4,
        max_external_core_calls=3,
        max_compute_units=16,
    )


@pytest.mark.parametrize(
    "field, alias",
    (
        ("max_steps", True),
        ("max_steps", 8.0),
        ("max_steps", "8"),
        ("max_tool_calls", False),
        ("max_tool_calls", 4.0),
        ("max_tool_calls", "4"),
        ("max_external_core_calls", True),
        ("max_external_core_calls", 3.0),
        ("max_external_core_calls", "3"),
        ("max_compute_units", True),
        ("max_compute_units", 16.0),
        ("max_compute_units", "16"),
    ),
)
def test_budget_restore_rejects_non_exact_integer_aliases(field, alias) -> None:
    state = _budget().to_state()
    state[field] = alias

    with pytest.raises(ValueError, match="execution budgets must be positive integers"):
        ExecutionBudget.from_state(state)


@pytest.mark.parametrize(
    "field, alias",
    (
        ("steps", True),
        ("steps", 1.0),
        ("steps", "1"),
        ("tool_calls", False),
        ("tool_calls", 1.0),
        ("tool_calls", "1"),
        ("external_core_calls", True),
        ("external_core_calls", 1.0),
        ("external_core_calls", "1"),
        ("compute_units", True),
        ("compute_units", 1.0),
        ("compute_units", "1"),
    ),
)
def test_counter_restore_rejects_non_exact_integer_aliases(field, alias) -> None:
    state = ExecutionCounters(steps=1, tool_calls=1, external_core_calls=1, compute_units=1).to_state()
    state[field] = alias

    with pytest.raises(ValueError, match="execution counters must be non-negative integers"):
        ExecutionCounters.from_state(state)


def test_budget_and_counter_canonical_roundtrip_is_unchanged() -> None:
    budget = _budget()
    counters = ExecutionCounters(steps=2, tool_calls=1, external_core_calls=1, compute_units=5)

    assert ExecutionBudget.from_state(budget.to_state()) == budget
    assert ExecutionCounters.from_state(counters.to_state()) == counters
