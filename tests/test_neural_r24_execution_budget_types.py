import pytest

from nolane.external_core.execution_types import ExecutionBudget


@pytest.mark.parametrize("value", (1.5, "2"))
def test_execution_budget_rejects_non_integer_step_limit(value):
    with pytest.raises(ValueError, match="execution budgets must be positive integers"):
        ExecutionBudget(
            max_steps=value,
            max_tool_calls=4,
            max_external_core_calls=4,
            max_compute_units=8,
        )


def test_execution_budget_accepts_exact_integer_limits():
    budget = ExecutionBudget(
        max_steps=4,
        max_tool_calls=4,
        max_external_core_calls=4,
        max_compute_units=8,
    )
    assert budget.max_steps == 4
