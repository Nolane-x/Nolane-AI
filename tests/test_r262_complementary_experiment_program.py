from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r262_complementary_experiment_program import (
    discover_complementary_experiment_structure,
    synthesize_complementary_experiment_program,
)


def _deadzone_mapping(context):
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


def _valid_deadzone_context(context):
    return float(context['low']) <= float(context['high'])


def _contexts():
    rows = []
    for low, high in ((-3.0, 2.0), (-1.0, 4.0), (-4.0, 1.0), (-5.0, 5.0)):
        for x in (-7.0, -4.0, -2.0, 0.0, 3.0, 6.0, 8.0):
            rows.append({'x': x, 'low': low, 'high': high})
    return tuple(rows)


def test_r262_discovers_complementary_pair_and_rejects_singletons():
    rows = _contexts()
    result = discover_complementary_experiment_structure(
        _deadzone_mapping, ('x', 'low', 'high'), (-10.0, 10.0), rows[:18], rows[18:],
        context_validator=_valid_deadzone_context, intervention_arity=1,
    )
    assert result.passed
    assert result.selected is not None
    assert result.selected.program.composition_op == 'add'
    assert {spec.bindings for spec in result.selected.program.interventions} == {
        ((1, -10.0),), ((2, 10.0),),
    }
    assert result.selected.left_alone_exact is False
    assert result.selected.right_alone_exact is False
    assert result.selected.proper_subset_failures == 2
    assert result.selected.left_essential_cases > 0
    assert result.selected.right_essential_cases > 0
    assert result.passing_programs == 1
    assert result.trainable_parameter_count == 0


def test_r262_fails_closed_on_invalid_interventions_and_is_rename_invariant():
    rows = _contexts()
    base = discover_complementary_experiment_structure(
        _deadzone_mapping, ('x', 'low', 'high'), (-10.0, 10.0), rows[:18], rows[18:],
        context_validator=_valid_deadzone_context, intervention_arity=1,
    )

    def rename_context(row):
        return {'q': row['x'], 'lo': row['low'], 'hi': row['high']}

    def renamed_oracle(context):
        return _deadzone_mapping({'x': context['q'], 'low': context['lo'], 'high': context['hi']})

    def renamed_valid(context):
        return float(context['lo']) <= float(context['hi'])

    renamed = discover_complementary_experiment_structure(
        renamed_oracle, ('q', 'lo', 'hi'), (-10.0, 10.0),
        tuple(rename_context(row) for row in rows[:18]),
        tuple(rename_context(row) for row in rows[18:]),
        context_validator=renamed_valid, intervention_arity=1,
    )
    assert base.passed and renamed.passed
    assert base.selected is not None and renamed.selected is not None
    assert base.selected.program.program_id == renamed.selected.program.program_id
    assert tuple(spec.bindings for spec in base.selected.program.interventions) == tuple(
        spec.bindings for spec in renamed.selected.program.interventions
    )
    assert base.invalid_interventions_rejected > 0
    assert renamed.invalid_interventions_rejected == base.invalid_interventions_rejected


def test_r262_hierarchical_probe_synthesis_beats_matched_flat_local_budget():
    rows = _contexts()
    need = OperatorInventionNeed(
        'bounded complementary deadzone decomposition', ('x', 'low', 'high'), 'out',
        constants=(-10.0, 10.0), max_depth=2, max_candidates=10000,
    )
    result = synthesize_complementary_experiment_program(
        _deadzone_mapping, ('x', 'low', 'high'), need, rows[:18], rows[18:],
        context_validator=_valid_deadzone_context, intervention_arity=1,
        probe_constants=(0.0,), probe_max_depth=2, probe_max_candidates=5000,
    )
    assert result.passed
    assert result.expression is not None
    assert result.baseline_passed is False
    assert result.baseline_candidates_considered == 10000
    assert sum(result.probe_candidates_considered) <= result.baseline_candidates_considered
    assert result.matched_synthesis_budget_respected is True
    assert result.validation_exact == result.validation_cases == 10
    assert all(exact < result.validation_cases for exact in result.singleton_validation_exact)
    assert result.trainable_parameter_count == 0
