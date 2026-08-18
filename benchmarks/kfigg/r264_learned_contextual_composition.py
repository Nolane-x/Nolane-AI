from __future__ import annotations

import math
from typing import Mapping

from cogcoder.r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary, evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r264_learned_contextual_composition import (
    discover_contextual_composition_structure,
    synthesize_contextual_composition_program,
)

_ROLES = ('x', 'lo', 'hi', 'left', 'middle', 'right')


def _band_rows() -> tuple[dict[str, float], ...]:
    rows: list[dict[str, float]] = []
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


def _band_oracle(row: Mapping[str, object]) -> float:
    x = float(row['x'])
    lo = float(row['lo'])
    hi = float(row['hi'])
    if x < lo:
        return float(row['left'])
    if x > hi:
        return float(row['right'])
    return float(row['middle'])


def _used_fields(expr: Expr) -> set[str]:
    if isinstance(expr, Field):
        return {expr.name}
    if isinstance(expr, Const):
        return set()
    if isinstance(expr, Unary):
        return _used_fields(expr.arg)
    if isinstance(expr, Binary):
        return _used_fields(expr.left) | _used_fields(expr.right)
    if isinstance(expr, IfElse):
        return _used_fields(expr.condition) | _used_fields(expr.when_true) | _used_fields(expr.when_false)
    raise TypeError(type(expr).__name__)


def _equivalent(actual: object, expected: object) -> bool:
    try:
        return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
    except (TypeError, ValueError, OverflowError):
        return actual == expected


def _configuration(
    ordered_fields: tuple[str, ...],
    field_to_role: Mapping[str, str],
) -> dict[str, object]:
    role_to_field = {role: field for field, role in field_to_role.items()}
    if set(role_to_field) != set(_ROLES):
        raise ValueError('configuration must represent every semantic role exactly once')

    def encode(row: Mapping[str, float]) -> dict[str, float]:
        return {role_to_field[role]: float(row[role]) for role in _ROLES}

    def oracle(row: Mapping[str, object]) -> float:
        return _band_oracle({role: row[role_to_field[role]] for role in _ROLES})

    rows = tuple(encode(row) for row in _band_rows())
    discovery = rows[:18]
    validation = rows[18:24]
    heldout = rows[24:]
    need = OperatorInventionNeed(
        'R2.64 authored learned contextual composition benchmark',
        ordered_fields,
        'out',
        constants=(0.0,),
        max_depth=3,
        max_candidates=25000,
    )
    receipt = synthesize_contextual_composition_program(
        oracle,
        ordered_fields,
        need,
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
    selected = receipt.structure.selected
    heldout_exact = 0
    if receipt.passed and receipt.expression is not None:
        for row in heldout:
            heldout_exact += int(_equivalent(evaluate_expr(receipt.expression, row), oracle(row)))

    selected_roles: list[str] = []
    shared_roles: list[str] = []
    used_fields: set[str] = set()
    program_id = None
    fixed_failed = False
    singleton_failures = 0
    selection_cases = 0
    selection_exact = 0
    composition_candidates = 0
    singleton_candidates = 0
    if selected is not None:
        selected_roles = sorted(field_to_role[ordered_fields[spec.bindings[0][0]]] for spec in selected.program.interventions)
        shared_roles = sorted(field_to_role[ordered_fields[position]] for position in selected.program.shared_positions)
        used_fields = _used_fields(selected.program.composition_expression)
        program_id = selected.program.program_id
        fixed_failed = not selected.r262_fixed_op_passed
        singleton_failures = sum(not value for value in selected.singleton_composition_passed)
        selection_cases = selected.selection_cases
        selection_exact = selected.selection_exact
        composition_candidates = selected.composition_candidates_considered
        singleton_candidates = sum(selected.singleton_candidates_considered)

    canonical_shared = {
        f'__f{position}'
        for position in (selected.program.shared_positions if selected is not None else ())
    }
    shared_context_only = all(
        field in {'__p0', '__p1'} or field in canonical_shared
        for field in used_fields
    )
    return {
        'passed': bool(receipt.passed and heldout_exact == len(heldout)),
        'program_id': program_id,
        'selected_roles': selected_roles,
        'shared_roles': shared_roles,
        'shared_context_only': shared_context_only,
        'both_probes_used': {'__p0', '__p1'} <= used_fields,
        'r262_fixed_op_failed': fixed_failed,
        'singleton_failures': singleton_failures,
        'selection_cases': selection_cases,
        'selection_exact': selection_exact,
        'probe_validation_cases': receipt.probe_validation_cases,
        'probe_validation_exact': receipt.probe_validation_exact,
        'final_validation_cases': receipt.final_validation_cases,
        'final_validation_exact': receipt.final_validation_exact,
        'heldout_cases': len(heldout),
        'heldout_exact': heldout_exact,
        'composition_candidates_considered': composition_candidates,
        'singleton_candidates_considered': singleton_candidates,
        'probe_candidates_considered': sum(receipt.probe_candidates_considered),
        'false_accepts': receipt.structure.false_accepts,
    }


def _fixed_op_negative() -> bool:
    rows = tuple(
        {'x': float(x), 'y': float(y)}
        for x, y in ((-5, 2), (-3, 7), (1, 9), (4, -6), (8, 3), (11, -4))
    )

    def oracle(row: Mapping[str, object]) -> float:
        return float(row['x']) + float(row['y'])

    receipt = discover_contextual_composition_structure(
        oracle,
        ('x', 'y'),
        (0.0,),
        rows[:4],
        rows[4:],
        composition_constants=(0.0,),
        composition_max_depth=1,
        composition_max_candidates_per_pair=3000,
        max_composition_candidates_total=12000,
    )
    return receipt.passed is False and receipt.false_accepts == 0


def _depth_zero_negative() -> bool:
    rows = _band_rows()
    receipt = discover_contextual_composition_structure(
        _band_oracle,
        _ROLES,
        (0.0,),
        rows[:18],
        rows[18:24],
        composition_constants=(0.0,),
        composition_max_depth=0,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
    )
    return receipt.passed is False and receipt.false_accepts == 0


def _budget_negative() -> bool:
    rows = _band_rows()
    receipt = discover_contextual_composition_structure(
        _band_oracle,
        _ROLES,
        (0.0,),
        rows[:18],
        rows[18:24],
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_pair=3,
        max_composition_candidates_total=15,
    )
    return receipt.passed is False and receipt.false_accepts == 0



def _nonfinite_negative() -> bool:
    rows = _band_rows()
    calls = 0

    def oracle(row: Mapping[str, object]) -> float:
        nonlocal calls
        calls += 1
        if calls == 2:
            return float('nan')
        return _band_oracle(row)

    receipt = discover_contextual_composition_structure(
        oracle,
        _ROLES,
        (0.0,),
        rows[:18],
        rows[18:24],
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
    )
    return (
        receipt.passed is False
        and receipt.reason.startswith('oracle_error:')
        and receipt.oracle_calls == 2
        and receipt.false_accepts == 0
    )


def _terminal_contradiction_negative() -> bool:
    rows = _band_rows()
    discovery = rows[:18]
    validation = rows[18:24]
    heldout = rows[24:]
    hidden = heldout[0]

    def oracle(row: Mapping[str, object]) -> float:
        value = _band_oracle(row)
        if all(float(row[key]) == float(hidden[key]) for key in _ROLES):
            return value + 101.0
        return value

    need = OperatorInventionNeed(
        'R2.64 hidden-terminal-contradiction negative',
        _ROLES,
        'out',
        constants=(0.0,),
        max_depth=3,
        max_candidates=25000,
    )
    receipt = synthesize_contextual_composition_program(
        oracle,
        _ROLES,
        need,
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
    if not receipt.passed or receipt.expression is None:
        return True
    exact = sum(
        int(_equivalent(evaluate_expr(receipt.expression, row), oracle(row)))
        for row in heldout
    )
    return exact < len(heldout)

def run_benchmark() -> dict[str, object]:
    base = _configuration(_ROLES, {role: role for role in _ROLES})
    rename_fields = ('q', 'a0', 'a1', 'v0', 'v1', 'v2')
    renamed = _configuration(rename_fields, dict(zip(rename_fields, _ROLES, strict=True)))
    permuted_roles = ('right', 'x', 'middle', 'hi', 'left', 'lo')
    permuted = _configuration(permuted_roles, {role: role for role in permuted_roles})
    rows = (base, renamed, permuted)

    result = {
        'milestone': 'R2.64',
        'capability': 'learned-contextual-causal-composition',
        'configurations': len(rows),
        'discoveries': sum(int(row['passed']) for row in rows),
        'full_program_successes': sum(int(row['passed']) for row in rows),
        'r262_fixed_op_failures': sum(int(row['r262_fixed_op_failed']) for row in rows),
        'singleton_composition_failures': sum(int(row['singleton_failures']) for row in rows),
        'selection_cases': sum(int(row['selection_cases']) for row in rows),
        'selection_exact': sum(int(row['selection_exact']) for row in rows),
        'probe_validation_cases': sum(int(row['probe_validation_cases']) for row in rows),
        'probe_validation_exact': sum(int(row['probe_validation_exact']) for row in rows),
        'final_validation_cases': sum(int(row['final_validation_cases']) for row in rows),
        'final_validation_exact': sum(int(row['final_validation_exact']) for row in rows),
        'heldout_cases': sum(int(row['heldout_cases']) for row in rows),
        'heldout_exact': sum(int(row['heldout_exact']) for row in rows),
        'rename_program_id_invariant': base['program_id'] == renamed['program_id'],
        'argument_permutation_tracks_roles': base['selected_roles'] == permuted['selected_roles'],
        'shared_context_only': all(bool(row['shared_context_only']) for row in rows),
        'both_probes_used': all(bool(row['both_probes_used']) for row in rows),
        'composition_candidates_considered': sum(int(row['composition_candidates_considered']) for row in rows),
        'singleton_candidates_considered': sum(int(row['singleton_candidates_considered']) for row in rows),
        'probe_candidates_considered': sum(int(row['probe_candidates_considered']) for row in rows),
        'fixed_op_negative_rejected': _fixed_op_negative(),
        'depth_zero_negative_rejected': _depth_zero_negative(),
        'budget_negative_rejected': _budget_negative(),
        'nonfinite_negative_rejected': _nonfinite_negative(),
        'terminal_contradiction_rejected': _terminal_contradiction_negative(),
        'false_accepts': sum(int(row['false_accepts']) for row in rows),
        'trainable_parameter_count': 0,
        'claim_boundary': (
            'Bounded learned contextual composition over two pure-input interventions and a finite trusted DSL, '
            'with shared untouched context only; not open-ended composition-language invention, 3+ intervention '
            'scaling, stateful experimentation, blind task discovery, broad repository autonomy, or AGI.'
        ),
    }
    return result


if __name__ == '__main__':
    import json
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
