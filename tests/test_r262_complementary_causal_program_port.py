from __future__ import annotations

from cogcoder.r262_complementary_experiment_program import discover_complementary_experiment_structure


def _deadzone(context):
    x = float(context['x'])
    low = float(context['low'])
    high = float(context['high'])
    if low > high:
        raise ValueError('low must be <= high')
    if x < low:
        return x - low
    if x > high:
        return x - high
    return 0.0


def _valid(context):
    return float(context['low']) <= float(context['high'])


def test_r262_port_preserves_complementary_pair_discovery() -> None:
    rows = tuple(
        {'x': x, 'low': low, 'high': high}
        for low, high in ((-3.0, 2.0), (-1.0, 4.0), (-4.0, 1.0), (-5.0, 5.0))
        for x in (-7.0, -4.0, -2.0, 0.0, 3.0, 6.0, 8.0)
    )
    result = discover_complementary_experiment_structure(
        _deadzone,
        ('x', 'low', 'high'),
        (-10.0, 10.0),
        rows[:18],
        rows[18:],
        context_validator=_valid,
        intervention_arity=1,
    )
    assert result.passed is True
    assert result.selected is not None
    assert result.selected.program.composition_op == 'add'
    assert {spec.bindings for spec in result.selected.program.interventions} == {
        ((1, -10.0),), ((2, 10.0),)
    }
    assert result.selected.proper_subset_failures == 2
    assert result.passing_programs == 1
    assert result.trainable_parameter_count == 0
