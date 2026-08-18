from __future__ import annotations

from typing import Mapping

from cogcoder.r256_operator_dsl import evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r260_complementary_experiment_program import synthesize_complementary_experiment_program


def _deadzone(x: float, low: float, high: float) -> float:
    if low > high:
        raise ValueError('low must be <= high')
    if x < low:
        return x - low
    if x > high:
        return x - high
    return 0.0


def _role_contexts() -> tuple[dict[str, float], ...]:
    rows: list[dict[str, float]] = []
    for low, high in ((-3.0, 2.0), (-1.0, 4.0), (-4.0, 1.0), (-5.0, 5.0)):
        for x in (-7.0, -4.0, -2.0, 0.0, 3.0, 6.0, 8.0):
            rows.append({'x': x, 'low': low, 'high': high})
    return tuple(rows)


def _challenge_roles() -> tuple[dict[str, float], ...]:
    return tuple(
        {'x': x, 'low': low, 'high': high}
        for x, low, high in (
            (-8.0, -4.0, 2.5), (-4.5, -4.0, 2.5), (-1.0, -4.0, 2.5), (4.0, -4.0, 2.5),
            (-6.0, -2.0, 5.5), (-2.5, -2.0, 5.5), (3.0, -2.0, 5.5), (8.0, -2.0, 5.5),
        )
    )


def _run_configuration(fields: tuple[str, str, str], roles: tuple[str, str, str]) -> dict[str, object]:
    if set(roles) != {'x', 'low', 'high'}:
        raise ValueError('roles must be a permutation of x/low/high')
    role_to_field = {role: field for field, role in zip(fields, roles, strict=True)}

    def convert(row: Mapping[str, float]) -> dict[str, float]:
        return {role_to_field[role]: float(row[role]) for role in ('x', 'low', 'high')}

    def oracle(context: Mapping[str, object]) -> float:
        return _deadzone(
            float(context[role_to_field['x']]),
            float(context[role_to_field['low']]),
            float(context[role_to_field['high']]),
        )

    def valid(context: Mapping[str, object]) -> bool:
        return float(context[role_to_field['low']]) <= float(context[role_to_field['high']])

    role_rows = _role_contexts()
    discovery = tuple(convert(row) for row in role_rows[:18])
    validation = tuple(convert(row) for row in role_rows[18:])
    challenge = tuple(convert(row) for row in _challenge_roles())
    need = OperatorInventionNeed(
        'R2.60 authored complementary experiment program',
        fields,
        'out',
        constants=(-10.0, 10.0),
        max_depth=2,
        max_candidates=10000,
    )
    receipt = synthesize_complementary_experiment_program(
        oracle,
        fields,
        need,
        discovery,
        validation,
        context_validator=valid,
        intervention_arity=1,
        probe_constants=(0.0,),
        probe_max_depth=2,
        probe_max_candidates=5000,
    )
    selected = receipt.structure.selected
    challenge_exact = 0
    singleton_challenge_exact = [0 for _ in receipt.probe_expressions]
    if receipt.passed and receipt.expression is not None:
        for context in challenge:
            expected = oracle(context)
            try:
                actual = evaluate_expr(receipt.expression, context)
            except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                actual = object()
            challenge_exact += int(actual == expected)
            for index, probe in enumerate(receipt.probe_expressions):
                try:
                    probe_actual = evaluate_expr(probe, context)
                except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                    probe_actual = object()
                singleton_challenge_exact[index] += int(probe_actual == expected)
    selected_bindings = tuple(spec.bindings for spec in selected.program.interventions) if selected is not None else ()
    return {
        'passed': bool(receipt.passed and challenge_exact == len(challenge)),
        'program_id': selected.program.program_id if selected is not None else None,
        'composition_op': selected.program.composition_op if selected is not None else None,
        'selected_bindings': selected_bindings,
        'proper_subset_failures': selected.proper_subset_failures if selected is not None else 0,
        'passing_programs': receipt.structure.passing_programs,
        'validation_cases': receipt.validation_cases,
        'validation_exact': receipt.validation_exact,
        'challenge_cases': len(challenge),
        'challenge_exact': challenge_exact,
        'singleton_challenge_exact': tuple(singleton_challenge_exact),
        'flat_baseline_passed': receipt.baseline_passed,
        'flat_baseline_candidates': receipt.baseline_candidates_considered,
        'probe_candidates': receipt.probe_candidates_considered,
        'matched_budget': receipt.matched_synthesis_budget_respected,
        'oracle_calls': receipt.structure.oracle_calls,
    }


def run_benchmark() -> dict[str, object]:
    base = _run_configuration(('x', 'low', 'high'), ('x', 'low', 'high'))
    renamed = _run_configuration(('q', 'lo', 'hi'), ('x', 'low', 'high'))
    permuted = _run_configuration(('hi_slot', 'x_slot', 'lo_slot'), ('high', 'x', 'low'))
    rows = (base, renamed, permuted)
    expected_base_roles = {((1, -10.0),), ((2, 10.0),)}
    expected_permuted_roles = {((2, -10.0),), ((0, 10.0),)}
    return {
        'milestone': 'R2.60',
        'capability': 'complementary-causal-experiment-program',
        'configurations': 3,
        'discoveries': sum(int(row['passed']) for row in rows),
        'flat_baseline_failures': sum(int(not row['flat_baseline_passed']) for row in rows),
        'full_program_successes': sum(int(row['passed']) for row in rows),
        'proper_subset_failures': sum(int(row['proper_subset_failures']) for row in rows),
        'validation_cases': sum(int(row['validation_cases']) for row in rows),
        'validation_exact': sum(int(row['validation_exact']) for row in rows),
        'challenge_cases': sum(int(row['challenge_cases']) for row in rows),
        'challenge_exact': sum(int(row['challenge_exact']) for row in rows),
        'rename_program_id_invariant': bool(base['program_id'] == renamed['program_id']),
        'argument_permutation_tracks_roles': bool(
            set(base['selected_bindings']) == expected_base_roles
            and set(permuted['selected_bindings']) == expected_permuted_roles
        ),
        'matched_synthesis_budget_respected': all(bool(row['matched_budget']) for row in rows),
        'flat_baseline_candidates_total': sum(int(row['flat_baseline_candidates']) for row in rows),
        'probe_synthesis_candidates_total': sum(sum(map(int, row['probe_candidates'])) for row in rows),
        'wrong_pair_false_accepts': sum(max(0, int(row['passing_programs']) - 1) for row in rows),
        'oracle_calls': sum(int(row['oracle_calls']) for row in rows),
        'composition_ops': sorted({str(row['composition_op']) for row in rows}),
        'trainable_parameter_count': 0,
        'claim_boundary': (
            'Bounded complementary two-experiment pure-input program discovery with matched local synthesis '
            'budget and invariance evidence; not open-ended experiment invention or broad autonomy.'
        ),
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
