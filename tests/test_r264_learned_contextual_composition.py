import math

import pytest

from cogcoder.r256_operator_dsl import Field, IfElse, evaluate_expr
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r264_learned_contextual_composition import (
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
    for index, (lo, hi, left, middle, right) in enumerate(configs):
        for x in (lo - 3.0, lo, (lo + hi) / 2.0, hi, hi + 3.0):
            rows.append({
                'x': x,
                'lo': lo,
                'hi': hi,
                'left': left,
                'middle': middle,
                'right': right,
                'case': index,
            })
    return tuple(rows)


def _need(fields=('x', 'lo', 'hi', 'left', 'middle', 'right')):
    return OperatorInventionNeed(
        'R2.64 learned contextual band composition',
        tuple(fields),
        'out',
        constants=(0.0,),
        max_depth=3,
        max_candidates=25000,
    )


def test_contextual_expression_search_learns_nested_decision_tree_under_budget():
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


def test_structure_discovers_contextual_pair_and_falsifies_r262_and_singletons():
    rows = _band_rows()
    discovery = tuple(dict(row) for row in rows[:18])
    validation = tuple(dict(row) for row in rows[18:])
    receipt = discover_contextual_composition_structure(
        _band_select,
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        (0.0,),
        discovery,
        validation,
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
    )
    assert receipt.passed is True
    assert receipt.selected is not None
    selected = receipt.selected
    positions = {spec.bindings[0][0] for spec in selected.program.interventions}
    assert len(positions) == 2
    assert set(selected.program.shared_positions).isdisjoint(positions)
    assert set(selected.program.shared_positions) | positions == set(range(6))
    assert {'__p0', '__p1'} <= set(selected.used_composition_fields)
    used_canonical_positions = {int(name[3:]) for name in selected.used_composition_fields if name.startswith('__f')}
    assert used_canonical_positions <= set(selected.program.shared_positions)
    assert selected.r262_fixed_op_passed is False
    assert selected.singleton_composition_passed == (False, False)
    assert selected.selection_exact == selected.selection_cases == len(discovery) + len(validation)
    assert receipt.false_accepts == 0
    assert receipt.trainable_parameter_count == 0


def test_structure_program_identity_is_rename_invariant_and_permutation_tracks_roles():
    rows = _band_rows()
    discovery = rows[:18]
    validation = rows[18:]
    base = discover_contextual_composition_structure(
        _band_select,
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        (0.0,), discovery, validation,
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
    )
    rename = {'x': 'q', 'lo': 'a0', 'hi': 'a1', 'left': 'v0', 'middle': 'v1', 'right': 'v2'}
    renamed_rows = tuple({rename.get(k, k): v for k, v in row.items() if k != 'case'} for row in rows)

    def renamed_oracle(context):
        return _band_select({
            'x': context['q'], 'lo': context['a0'], 'hi': context['a1'],
            'left': context['v0'], 'middle': context['v1'], 'right': context['v2'],
        })

    renamed = discover_contextual_composition_structure(
        renamed_oracle,
        ('q', 'a0', 'a1', 'v0', 'v1', 'v2'),
        (0.0,), renamed_rows[:18], renamed_rows[18:],
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
    )
    assert base.passed and renamed.passed
    assert base.selected.program.program_id == renamed.selected.program.program_id
    assert base.selected.program.shared_positions == renamed.selected.program.shared_positions
    assert tuple(spec.bindings for spec in base.selected.program.interventions) == tuple(
        spec.bindings for spec in renamed.selected.program.interventions
    )
    base_roles = {('x', 'lo', 'hi', 'left', 'middle', 'right')[spec.bindings[0][0]] for spec in base.selected.program.interventions}

    order = ('right', 'x', 'middle', 'hi', 'left', 'lo')
    perm_rows = tuple({field: row[field] for field in order} for row in rows)
    perm = discover_contextual_composition_structure(
        _band_select,
        order,
        (0.0,), perm_rows[:18], perm_rows[18:],
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
    )
    assert perm.passed
    fixed_roles = {order[spec.bindings[0][0]] for spec in perm.selected.program.interventions}
    assert fixed_roles == base_roles


def test_full_program_synthesizes_probes_substitutes_composition_and_validates():
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
    assert all(math.isclose(float(evaluate_expr(receipt.expression, row)), _band_select(row)) for row in heldout)


def test_budget_and_nonfinite_paths_fail_closed():
    rows = _band_rows()
    tiny = discover_contextual_composition_structure(
        _band_select,
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        (0.0,), rows[:18], rows[18:],
        composition_max_depth=2,
        composition_max_candidates_per_pair=3,
        max_composition_candidates_total=15,
    )
    assert tiny.passed is False
    assert tiny.reason in {'composition_budget_exhausted', 'no_contextual_composition'}
    assert tiny.false_accepts == 0

    def bad_oracle(context):
        if float(context['x']) == float(context['lo']):
            return float('nan')
        return _band_select(context)

    bad = discover_contextual_composition_structure(
        bad_oracle,
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        (0.0,), rows[:18], rows[18:],
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
    )
    assert bad.passed is False
    assert bad.reason.startswith('oracle_error:')
    assert bad.false_accepts == 0


def test_oracle_failure_receipt_counts_attempted_target_calls_exactly():
    rows = _band_rows()
    attempted = 0

    def failing_oracle(context):
        nonlocal attempted
        attempted += 1
        if attempted == 2:
            raise RuntimeError('target oracle failed')
        return _band_select(context)

    receipt = discover_contextual_composition_structure(
        failing_oracle,
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        (0.0,),
        rows[:18],
        rows[18:27],
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
    )
    assert receipt.passed is False
    assert receipt.reason.startswith('oracle_error:RuntimeError:')
    assert attempted == 2
    assert receipt.oracle_calls == attempted
    assert receipt.false_accepts == 0
