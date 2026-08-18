from __future__ import annotations

import math
from typing import Callable, Mapping

from cogcoder.r256_operator_dsl import evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r260_complementary_experiment_program import synthesize_complementary_experiment_program

_FIELDS = ('v0', 'v1', 'v2')  # opaque ordered roles: x, low, high


def _equivalent(actual: object, expected: object) -> bool:
    try:
        return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
    except (TypeError, ValueError, OverflowError):
        return False


def _make_context(x: float, low: float, high: float) -> dict[str, float]:
    return {'v0': float(x), 'v1': float(low), 'v2': float(high)}


def _discovery_contexts() -> tuple[dict[str, float], ...]:
    rows: list[dict[str, float]] = []
    for low, high, xs in (
        (-3.0, 2.0, (-7.0, -4.0, -2.0, 0.0, 3.0, 6.0)),
        (-1.0, 4.0, (-6.0, -2.0, 1.0, 3.0, 5.0, 8.0)),
        (-4.0, 1.0, (-8.0, -5.0, -1.0, 0.0, 2.0, 7.0)),
    ):
        rows.extend(_make_context(x, low, high) for x in xs)
    return tuple(rows)


def _validation_contexts() -> tuple[dict[str, float], ...]:
    return tuple(
        _make_context(x, low, high)
        for x, low, high in (
            (-9.0, -5.0, 3.0), (-6.0, -5.0, 3.0), (-1.0, -5.0, 3.0), (4.0, -5.0, 3.0),
            (8.0, -5.0, 3.0), (-7.0, -2.0, 5.0), (-3.0, -2.0, 5.0), (2.0, -2.0, 5.0),
            (6.0, -2.0, 5.0), (9.0, -2.0, 5.0),
        )
    )


def _challenge_contexts() -> tuple[dict[str, float], ...]:
    return tuple(
        _make_context(x, low, high)
        for x, low, high in (
            (-8.5, -4.5, 2.5), (-5.0, -4.5, 2.5), (-2.0, -4.5, 2.5), (3.5, -4.5, 2.5),
            (-6.5, -1.5, 4.5), (-2.5, -1.5, 4.5), (4.0, -1.5, 4.5), (8.5, -1.5, 4.5),
        )
    )


def _heldout_contexts() -> tuple[dict[str, float], ...]:
    rows: list[dict[str, float]] = []
    threshold_pairs = ((-6.0, -0.5), (-3.5, 1.5), (-2.5, 6.0), (-7.0, 4.0))
    fractions = (-1.25, -0.2, 0.2, 0.55, 1.15, 1.7)
    for low, high in threshold_pairs:
        span = high - low
        for frac in fractions:
            rows.append(_make_context(low + frac * span, low, high))
    return tuple(rows)


def run_external_transfer(
    deadzone_callable: Callable[[float, float, float], object],
    *,
    source_id: str,
    source_commit: str,
) -> dict[str, object]:
    if not callable(deadzone_callable):
        raise TypeError('deadzone_callable must be callable')

    def oracle(context: Mapping[str, object]) -> float:
        return float(deadzone_callable(float(context['v0']), float(context['v1']), float(context['v2'])))

    def valid(context: Mapping[str, object]) -> bool:
        return float(context['v1']) <= float(context['v2'])

    discovery = _discovery_contexts()
    validation = _validation_contexts()
    challenge = _challenge_contexts()
    heldout = _heldout_contexts()
    need = OperatorInventionNeed(
        'R2.60 external complementary experiment program',
        _FIELDS,
        'out',
        constants=(-10.0, 10.0),
        max_depth=2,
        max_candidates=10000,
    )
    receipt = synthesize_complementary_experiment_program(
        oracle,
        _FIELDS,
        need,
        discovery,
        validation,
        context_validator=valid,
        intervention_arity=1,
        composition_ops=('add', 'sub', 'rsub', 'mul', 'min', 'max'),
        probe_constants=(0.0,),
        probe_max_depth=2,
        probe_max_candidates=5000,
    )
    selected = receipt.structure.selected
    expression = receipt.expression
    challenge_exact = 0
    heldout_exact = 0
    singleton_challenge = [0 for _ in receipt.probe_expressions]
    extra_oracle_calls = 0

    if receipt.passed and expression is not None:
        for context in challenge:
            expected = oracle(context)
            extra_oracle_calls += 1
            try:
                actual = evaluate_expr(expression, context)
            except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                actual = object()
            challenge_exact += int(_equivalent(actual, expected))
            for index, probe in enumerate(receipt.probe_expressions):
                try:
                    probe_actual = evaluate_expr(probe, context)
                except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                    probe_actual = object()
                singleton_challenge[index] += int(_equivalent(probe_actual, expected))
        for context in heldout:
            expected = oracle(context)
            extra_oracle_calls += 1
            try:
                actual = evaluate_expr(expression, context)
            except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                actual = object()
            heldout_exact += int(_equivalent(actual, expected))

    passed = bool(
        receipt.passed
        and selected is not None
        and expression is not None
        and challenge_exact == len(challenge)
        and heldout_exact == len(heldout)
        and len(singleton_challenge) == 2
        and all(value < len(challenge) for value in singleton_challenge)
    )
    return {
        'passed': passed,
        'source_id': str(source_id),
        'source_commit': str(source_commit),
        'source_exposure': 'io_only',
        'external_function_family': 'deadzone',
        'researcher_selected_function_family': True,
        'blind_external_task_selection': False,
        'host_selected_intervention': False,
        'intervention_anchor_source': 'program_need.constants',
        'derived_anchor_values': [-10.0, 10.0],
        'composition_language': ['add', 'sub', 'rsub', 'mul', 'min', 'max'],
        'composition_op': selected.program.composition_op if selected is not None else None,
        'selected_program_id': selected.program.program_id if selected is not None else None,
        'selected_bindings': [
            [[position, value] for position, value in spec.bindings]
            for spec in selected.program.interventions
        ] if selected is not None else [],
        'proper_subset_failures': selected.proper_subset_failures if selected is not None else 0,
        'left_essential_cases': selected.left_essential_cases if selected is not None else 0,
        'right_essential_cases': selected.right_essential_cases if selected is not None else 0,
        'legal_interventions': receipt.structure.legal_interventions,
        'invalid_interventions_rejected': receipt.structure.invalid_interventions_rejected,
        'pair_operation_candidates_considered': receipt.structure.pair_operation_candidates_considered,
        'passing_programs': receipt.structure.passing_programs,
        'flat_baseline_passed': receipt.baseline_passed,
        'flat_baseline_candidates': receipt.baseline_candidates_considered,
        'probe_synthesis_candidates': list(receipt.probe_candidates_considered),
        'probe_synthesis_candidates_total': sum(receipt.probe_candidates_considered),
        'matched_synthesis_budget_respected': receipt.matched_synthesis_budget_respected,
        'validation_cases': receipt.validation_cases,
        'validation_exact': receipt.validation_exact,
        'singleton_validation_exact': list(receipt.singleton_validation_exact),
        'challenge_cases': len(challenge),
        'challenge_exact': challenge_exact,
        'singleton_challenge_exact': singleton_challenge,
        'heldout_cases': len(heldout),
        'heldout_exact': heldout_exact,
        'oracle_calls_total': receipt.structure.oracle_calls + extra_oracle_calls,
        'trainable_parameter_count': 0,
        'claim_boundary': (
            'Bounded two-experiment pure-input causal program discovery on a researcher-selected '
            'independently sourced I/O-only deadzone family; not open-ended experiment invention, '
            'blind external discovery, effectful intervention design, or general program synthesis.'
        ),
    }


if __name__ == '__main__':
    raise SystemExit('Pass an external oracle callable from a hosted verification harness.')
