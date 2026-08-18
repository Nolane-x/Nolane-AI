import math

from cogcoder.r256_operator_dsl import IfElse, evaluate_expr
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r266_learned_contextual_composition import (
    discover_contextual_composition_structure,
    synthesize_contextual_composition_program,
    synthesize_contextual_expression,
)


def _band_select(context):
    x = float(context['x'])
    lo = float(context['lo'])
    hi = float(context['hi'])
    if x < lo:
        return float(context['left'])
    if x > hi:
        return float(context['right'])
    return float(context['middle'])


def _band_rows():
    rows = []
    configs = (
        (-3.0, 2.0, -7.0, 4.0, -5.0),
        (-1.0, 4.0, 6.0, -3.0, 9.0),
        (-5.0, 1.0, -8.0, 5.0, 2.0),
        (0.0, 6.0, 3.0, -6.0, -4.0),
        (-4.0, 3.0, 8.0, 2.0, -9.0),
        (-2.0, 5.0, -6.0, -1.0, 7.0),
    )
    for lo, hi, left, middle, right in configs:
        for x in (lo - 3.0, lo, (lo + hi) / 2.0, hi, hi + 3.0):
            rows.append({
                'x': x,
                'lo': lo,
                'hi': hi,
                'left': left,
                'middle': middle,
                'right': right,
            })
    return tuple(rows)


def _need(fields=('x', 'lo', 'hi', 'left', 'middle', 'right')):
    return OperatorInventionNeed(
        'R2.66 learned contextual band composition',
        tuple(fields),
        'out',
        constants=(0.0,),
        max_depth=3,
        max_candidates=25000,
    )


def _discover(order=('x', 'lo', 'hi', 'left', 'middle', 'right')):
    rows = _band_rows()
    projected = tuple({name: row[name] for name in order} for row in rows)
    return discover_contextual_composition_structure(
        _band_select,
        order,
        (0.0,),
        projected[:18],
        projected[18:],
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
    )


def _selected_roles(receipt, order):
    assert receipt.selected is not None
    return frozenset(
        order[position]
        for spec in receipt.selected.program.interventions
        for position, _value in spec.bindings
    )


def test_r266_contextual_expression_learns_bounded_conditional_router():
    examples = (
        OperatorExample('a', {'x': -2.0, 'pivot': 0.0, 'left': -7.0, 'right': 9.0}, -7.0),
        OperatorExample('b', {'x': -1.0, 'pivot': 0.0, 'left': 6.0, 'right': -4.0}, 6.0),
        OperatorExample('c', {'x': 1.0, 'pivot': 0.0, 'left': 8.0, 'right': -5.0}, -5.0),
        OperatorExample('d', {'x': 2.0, 'pivot': 0.0, 'left': -3.0, 'right': 7.0}, 7.0),
    )
    receipt = synthesize_contextual_expression(
        ('x', 'pivot', 'left', 'right'),
        (0.0,),
        examples,
        max_depth=2,
        max_candidates=5000,
    )
    assert receipt.passed is True
    assert isinstance(receipt.expression, IfElse)
    assert receipt.expression.depth <= 2
    assert receipt.candidates_considered <= 5000
    assert all(evaluate_expr(receipt.expression, row.context) == row.expected for row in examples)


def test_r266_discovers_two_probe_contextual_program_without_smuggling():
    receipt = _discover()
    assert receipt.passed is True
    assert receipt.selected is not None
    selected = receipt.selected
    fixed_positions = {
        position
        for spec in selected.program.interventions
        for position, _value in spec.bindings
    }
    assert len(fixed_positions) == 2
    assert set(selected.program.shared_positions).isdisjoint(fixed_positions)
    assert set(selected.program.shared_positions) | fixed_positions == set(range(6))
    assert {'__p0', '__p1'} <= set(selected.used_composition_fields)
    used_context_positions = {
        int(name[3:])
        for name in selected.used_composition_fields
        if name.startswith('__f')
    }
    assert used_context_positions <= set(selected.program.shared_positions)
    assert selected.r262_fixed_op_passed is False
    assert selected.singleton_composition_passed == (False, False)
    assert selected.selection_exact == selected.selection_cases == len(_band_rows())
    assert receipt.false_accepts == 0
    assert receipt.trainable_parameter_count == 0


def test_r266_program_identity_survives_rename_and_semantic_roles_survive_permutation():
    rows = _band_rows()
    base_order = ('x', 'lo', 'hi', 'left', 'middle', 'right')
    base = _discover(base_order)
    assert base.passed is True

    rename = {'x': 'q', 'lo': 'a0', 'hi': 'a1', 'left': 'v0', 'middle': 'v1', 'right': 'v2'}
    renamed_order = tuple(rename[name] for name in base_order)
    renamed_rows = tuple({rename[k]: v for k, v in row.items()} for row in rows)

    def renamed_oracle(context):
        return _band_select({
            'x': context['q'],
            'lo': context['a0'],
            'hi': context['a1'],
            'left': context['v0'],
            'middle': context['v1'],
            'right': context['v2'],
        })

    renamed = discover_contextual_composition_structure(
        renamed_oracle,
        renamed_order,
        (0.0,),
        renamed_rows[:18],
        renamed_rows[18:],
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
    )
    assert renamed.passed is True
    assert base.selected.program.program_id == renamed.selected.program.program_id

    perm_order = ('right', 'x', 'middle', 'hi', 'left', 'lo')
    perm = _discover(perm_order)
    assert perm.passed is True
    assert _selected_roles(base, base_order) == _selected_roles(perm, perm_order)
    assert base.false_accepts == perm.false_accepts == 0


def test_r266_full_program_synthesizes_probes_and_passes_terminal_heldout():
    rows = _band_rows()
    discovery = rows[:18]
    validation = rows[18:24]
    heldout = rows[24:]
    receipt = synthesize_contextual_composition_program(
        _band_select,
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        _need(),
        discovery,
        validation,
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
        probe_constants=(0.0,),
        probe_max_depth=3,
        probe_max_candidates=20000,
    )
    assert receipt.passed is True
    assert receipt.expression is not None
    assert len(receipt.probe_expressions) == 2
    assert receipt.probe_validation_exact == receipt.probe_validation_cases * 2
    assert receipt.final_validation_exact == receipt.final_validation_cases == len(validation)
    assert receipt.structure.selected.r262_fixed_op_passed is False
    assert receipt.structure.selected.singleton_composition_passed == (False, False)
    assert all(
        math.isclose(float(evaluate_expr(receipt.expression, row)), _band_select(row))
        for row in heldout
    )


def test_r266_budget_nonfinite_and_oracle_failure_paths_fail_closed_with_accounting():
    rows = _band_rows()
    tiny = discover_contextual_composition_structure(
        _band_select,
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        (0.0,),
        rows[:18],
        rows[18:],
        composition_max_depth=2,
        composition_max_candidates_per_pair=3,
        max_composition_candidates_total=15,
    )
    assert tiny.passed is False
    assert tiny.reason in {'composition_budget_exhausted', 'no_contextual_composition'}
    assert tiny.false_accepts == 0

    def nonfinite(context):
        if float(context['x']) == float(context['lo']):
            return float('nan')
        return _band_select(context)

    bad = discover_contextual_composition_structure(
        nonfinite,
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        (0.0,),
        rows[:18],
        rows[18:],
    )
    assert bad.passed is False
    assert bad.reason.startswith('oracle_error:')
    assert bad.false_accepts == 0

    attempted = 0

    def failing(context):
        nonlocal attempted
        attempted += 1
        if attempted == 2:
            raise RuntimeError('target oracle failed')
        return _band_select(context)

    failed = discover_contextual_composition_structure(
        failing,
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        (0.0,),
        rows[:18],
        rows[18:27],
    )
    assert failed.passed is False
    assert failed.reason.startswith('oracle_error:RuntimeError:')
    assert failed.oracle_calls == attempted == 2
    assert failed.false_accepts == 0
