import pytest

from nolane.external_core.execution_types import ExecutionCounters


_COUNTER_FIELDS = (
    'steps',
    'tool_calls',
    'external_core_calls',
    'compute_units',
)


@pytest.mark.parametrize('field', _COUNTER_FIELDS)
def test_direct_execution_counter_rejects_fractional_authority(field: str) -> None:
    with pytest.raises(ValueError, match='execution counters must be non-negative integers'):
        ExecutionCounters(**{field: 1.5})


@pytest.mark.parametrize('field', _COUNTER_FIELDS)
def test_direct_execution_counter_rejects_string_authority(field: str) -> None:
    with pytest.raises(ValueError, match='execution counters must be non-negative integers'):
        ExecutionCounters(**{field: '2'})


def test_execution_counter_accepts_non_negative_exact_integer_authority() -> None:
    counters = ExecutionCounters(
        steps=0,
        tool_calls=1,
        external_core_calls=2,
        compute_units=3,
    )

    assert counters.to_state() == {
        'steps': 0,
        'tool_calls': 1,
        'external_core_calls': 2,
        'compute_units': 3,
    }
