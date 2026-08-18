from __future__ import annotations

import math
from typing import Mapping

from cogcoder.r256_operator_dsl import evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r266_learned_contextual_composition import (
    discover_contextual_composition_structure,
    synthesize_contextual_composition_program,
)

_ROLES = ('x', 'lo', 'hi', 'left', 'middle', 'right')


def _rows() -> tuple[dict[str, float], ...]:
    configs = (
        (-3.0, 2.0, -7.0, 4.0, -5.0),
        (-1.0, 4.0, 6.0, -3.0, 9.0),
        (-5.0, 1.0, -8.0, 5.0, 2.0),
        (0.0, 6.0, 3.0, -6.0, -4.0),
        (-4.0, 3.0, 8.0, 2.0, -9.0),
        (-2.0, 5.0, -6.0, -1.0, 7.0),
    )
    out: list[dict[str, float]] = []
    for lo, hi, left, middle, right in configs:
        for x in (lo - 3.0, lo, (lo + hi) / 2.0, hi, hi + 3.0):
            out.append({
                'x': x,
                'lo': lo,
                'hi': hi,
                'left': left,
                'middle': middle,
                'right': right,
            })
    return tuple(out)


def _oracle(row: Mapping[str, object]) -> float:
    x = float(row['x'])
    lo = float(row['lo'])
    hi = float(row['hi'])
    if x < lo:
        return float(row['left'])
    if x > hi:
        return float(row['right'])
    return float(row['middle'])


def _eq(actual: object, expected: object) -> bool:
    try:
        return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
    except (TypeError, ValueError, OverflowError):
        return actual == expected


def _case(ordered_fields: tuple[str, ...], field_to_role: Mapping[str, str]) -> dict[str, object]:
    role_to_field = {role: field for field, role in field_to_role.items()}
    if set(role_to_field) != set(_ROLES):
        raise ValueError('configuration must represent every role exactly once')

    def encode(row: Mapping[str, float]) -> dict[str, float]:
        return {role_to_field[role]: float(row[role]) for role in _ROLES}

    def mapped_oracle(row: Mapping[str, object]) -> float:
        return _oracle({role: row[role_to_field[role]] for role in _ROLES})

    rows = tuple(encode(row) for row in _rows())
    discovery, validation, heldout = rows[:18], rows[18:24], rows[24:]
    need = OperatorInventionNeed(
        'R2.66 authored contextual composition',
        ordered_fields,
        'out',
        constants=(0.0,),
        max_depth=3,
        max_candidates=25000,
    )
    receipt = synthesize_contextual_composition_program(
        mapped_oracle,
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
        heldout_exact = sum(
            int(_eq(evaluate_expr(receipt.expression, row), mapped_oracle(row)))
            for row in heldout
        )

    selected_roles: list[str] = []
    shared_roles: list[str] = []
    fixed_failed = False
    singleton_failed = False
    program_id = None
    no_smuggling = False
    both_probes = False
    selection_exact = 0
    selection_cases = 0
    if selected is not None:
        selected_roles = sorted(
            field_to_role[ordered_fields[spec.bindings[0][0]]]
            for spec in selected.program.interventions
        )
        shared_roles = sorted(
            field_to_role[ordered_fields[position]]
            for position in selected.program.shared_positions
        )
        fixed_positions = {
            position
            for spec in selected.program.interventions
            for position, _value in spec.bindings
        }
        used = set(selected.used_composition_fields)
        used_positions = {int(name[3:]) for name in used if name.startswith('__f')}
        no_smuggling = (
            used_positions <= set(selected.program.shared_positions)
            and set(selected.program.shared_positions).isdisjoint(fixed_positions)
        )
        both_probes = {'__p0', '__p1'} <= used
        fixed_failed = selected.r262_fixed_op_passed is False
        singleton_failed = selected.singleton_composition_passed == (False, False)
        program_id = selected.program.program_id
        selection_exact = selected.selection_exact
        selection_cases = selected.selection_cases

    return {
        'passed': bool(receipt.passed and heldout_exact == len(heldout)),
        'program_id': program_id,
        'selected_roles': selected_roles,
        'shared_roles': shared_roles,
        'no_smuggling': no_smuggling,
        'both_probes_used': both_probes,
        'fixed_op_baseline_failed': fixed_failed,
        'singletons_failed': singleton_failed,
        'selection_exact': selection_exact,
        'selection_cases': selection_cases,
        'probe_validation_exact': receipt.probe_validation_exact,
        'probe_validation_cases': receipt.probe_validation_cases,
        'final_validation_exact': receipt.final_validation_exact,
        'final_validation_cases': receipt.final_validation_cases,
        'heldout_exact': heldout_exact,
        'heldout_cases': len(heldout),
        'composition_candidates': receipt.structure.composition_candidates_considered,
        'singleton_candidates': receipt.structure.singleton_candidates_considered,
        'probe_candidates': sum(receipt.probe_candidates_considered),
        'false_accepts': receipt.structure.false_accepts,
    }


def _budget_negative() -> bool:
    rows = _rows()
    result = discover_contextual_composition_structure(
        _oracle,
        _ROLES,
        (0.0,),
        rows[:18],
        rows[18:24],
        composition_max_depth=2,
        composition_max_candidates_per_pair=3,
        max_composition_candidates_total=15,
    )
    return result.passed is False and result.false_accepts == 0


def _nonfinite_negative() -> bool:
    rows = _rows()
    calls = 0

    def bad(row):
        nonlocal calls
        calls += 1
        if calls == 2:
            return float('nan')
        return _oracle(row)

    result = discover_contextual_composition_structure(
        bad,
        _ROLES,
        (0.0,),
        rows[:18],
        rows[18:24],
    )
    return (
        result.passed is False
        and result.reason.startswith('oracle_error:')
        and result.oracle_calls == calls == 2
        and result.false_accepts == 0
    )


def _fixed_op_negative() -> bool:
    rows = tuple(
        {'x': float(x), 'y': float(y)}
        for x, y in ((-5, 2), (-3, 7), (1, 9), (4, -6), (8, 3), (11, -4))
    )

    def add(row):
        return float(row['x']) + float(row['y'])

    result = discover_contextual_composition_structure(
        add,
        ('x', 'y'),
        (0.0,),
        rows[:4],
        rows[4:],
        composition_max_depth=1,
        composition_max_candidates_per_pair=3000,
        max_composition_candidates_total=12000,
    )
    return result.passed is False and result.false_accepts == 0


def _terminal_contradiction_negative() -> bool:
    rows = _rows()
    discovery, validation, heldout = rows[:18], rows[18:24], rows[24:]
    hidden = heldout[0]

    def shifted(row):
        value = _oracle(row)
        if all(float(row[key]) == float(hidden[key]) for key in _ROLES):
            return value + 101.0
        return value

    need = OperatorInventionNeed(
        'R2.66 hidden terminal contradiction',
        _ROLES,
        'out',
        constants=(0.0,),
        max_depth=3,
        max_candidates=25000,
    )
    result = synthesize_contextual_composition_program(
        shifted,
        _ROLES,
        need,
        discovery,
        validation,
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
        probe_max_depth=3,
        probe_max_candidates=20000,
    )
    if not result.passed or result.expression is None:
        return True
    exact = sum(
        int(_eq(evaluate_expr(result.expression, row), shifted(row)))
        for row in heldout
    )
    return exact < len(heldout)


def run_benchmark() -> dict[str, object]:
    base = _case(_ROLES, {role: role for role in _ROLES})
    renamed_fields = ('q', 'a0', 'a1', 'v0', 'v1', 'v2')
    renamed = _case(renamed_fields, dict(zip(renamed_fields, _ROLES, strict=True)))
    permuted_roles = ('right', 'x', 'middle', 'hi', 'left', 'lo')
    permuted = _case(permuted_roles, {role: role for role in permuted_roles})
    cases = (base, renamed, permuted)

    all_passed = bool(
        all(case['passed'] for case in cases)
        and base['program_id'] == renamed['program_id']
        and base['selected_roles'] == permuted['selected_roles']
        and all(case['no_smuggling'] for case in cases)
        and all(case['both_probes_used'] for case in cases)
        and all(case['fixed_op_baseline_failed'] for case in cases)
        and all(case['singletons_failed'] for case in cases)
        and _fixed_op_negative()
        and _budget_negative()
        and _nonfinite_negative()
        and _terminal_contradiction_negative()
        and sum(case['false_accepts'] for case in cases) == 0
    )
    return {
        'milestone': 'R2.66',
        'capability': 'learned-contextual-causal-composition',
        'all_gates_pass': all_passed,
        'configurations': len(cases),
        'configuration_successes': sum(int(case['passed']) for case in cases),
        'rename_program_id_invariant': base['program_id'] == renamed['program_id'],
        'argument_permutation_tracks_roles': base['selected_roles'] == permuted['selected_roles'],
        'no_smuggling': all(bool(case['no_smuggling']) for case in cases),
        'both_probes_used': all(bool(case['both_probes_used']) for case in cases),
        'fixed_op_baseline_failures': sum(int(case['fixed_op_baseline_failed']) for case in cases),
        'singleton_ablation_failures': sum(int(case['singletons_failed']) for case in cases),
        'selection_cases': sum(int(case['selection_cases']) for case in cases),
        'selection_exact': sum(int(case['selection_exact']) for case in cases),
        'probe_validation_cases': sum(int(case['probe_validation_cases']) for case in cases),
        'probe_validation_exact': sum(int(case['probe_validation_exact']) for case in cases),
        'final_validation_cases': sum(int(case['final_validation_cases']) for case in cases),
        'final_validation_exact': sum(int(case['final_validation_exact']) for case in cases),
        'heldout_cases': sum(int(case['heldout_cases']) for case in cases),
        'heldout_exact': sum(int(case['heldout_exact']) for case in cases),
        'composition_candidates_considered': sum(int(case['composition_candidates']) for case in cases),
        'singleton_candidates_considered': sum(int(case['singleton_candidates']) for case in cases),
        'probe_candidates_considered': sum(int(case['probe_candidates']) for case in cases),
        'fixed_op_negative_rejected': _fixed_op_negative(),
        'budget_negative_rejected': _budget_negative(),
        'nonfinite_negative_rejected': _nonfinite_negative(),
        'terminal_contradiction_rejected': _terminal_contradiction_negative(),
        'false_accepts': sum(int(case['false_accepts']) for case in cases),
        'trainable_parameter_count': 0,
        'claim_boundary': (
            'Bounded learned contextual composition over exactly two pure-input interventions and a finite trusted DSL; '
            'not primitive-language invention, 3+ intervention scaling, effectful experimentation, blind discovery, or AGI.'
        ),
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
