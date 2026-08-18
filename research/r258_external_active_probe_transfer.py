from __future__ import annotations

import math
from typing import Callable, Mapping

from benchmarks.kfigg.r257_verified_vocabulary_growth import build_promoted_vocabulary
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r257_vocabulary import evaluate_with_vocabulary
from cogcoder.r257_vocabulary_synthesis import synthesize_with_vocabulary
from cogcoder.r258_active_probe import ProbeBudget, discover_verified_subgoal


def _call_oracle(oracle: Callable[..., object], context: Mapping[str, object]) -> float:
    value = float(oracle(
        float(context['x']), float(context['a']), float(context['b']),
        float(context['fa']), float(context['fb']),
    ))
    if not math.isfinite(value):
        raise ValueError('external oracle returned non-finite value')
    return value


def _context(row: tuple[float, float, float, float, float]) -> dict[str, float]:
    return dict(zip(('x', 'a', 'b', 'fa', 'fb'), row))


def _training_cases() -> tuple[tuple[float, float, float, float, float], ...]:
    return (
        (-4.0, 0.0, 8.0, 2.0, 10.0), (0.0, 0.0, 8.0, 2.0, 10.0),
        (2.0, 0.0, 8.0, 2.0, 10.0), (4.0, 0.0, 8.0, 2.0, 10.0),
        (6.0, 0.0, 8.0, 2.0, 10.0), (8.0, 0.0, 8.0, 2.0, 10.0),
        (12.0, 0.0, 8.0, 2.0, 10.0), (0.0, -4.0, 4.0, -2.0, 6.0),
    )


def _challenge_cases() -> tuple[tuple[float, float, float, float, float], ...]:
    return (
        (-6.0, -4.0, 4.0, -2.0, 6.0), (-4.0, -4.0, 4.0, -2.0, 6.0),
        (-2.0, -4.0, 4.0, -2.0, 6.0), (2.0, -4.0, 4.0, -2.0, 6.0),
        (4.0, -4.0, 4.0, -2.0, 6.0), (8.0, -4.0, 4.0, -2.0, 6.0),
        (4.0, 2.0, 10.0, -4.0, 4.0), (8.0, 2.0, 10.0, -4.0, 4.0),
    )


def _heldout_cases() -> tuple[tuple[float, float, float, float, float], ...]:
    rows = []
    for a, b, fa, fb in ((0.0, 8.0, 1.0, 5.0), (-4.0, 4.0, -2.0, 6.0), (2.0, 10.0, -4.0, 4.0)):
        width = b - a
        for t in (-0.5, 0.0, 0.125, 0.375, 0.625, 0.875, 1.0, 1.5):
            rows.append((a + t * width, a, b, fa, fb))
    return tuple(rows)


def run_external_transfer(
    oracle: Callable[..., object],
    *,
    source_id: str,
    source_commit: str,
) -> dict[str, object]:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    vocabulary, _lifecycle, selected = build_promoted_vocabulary()
    learned_digests = tuple(row.abstraction.abstraction_id for row in selected)

    train = tuple(
        OperatorExample(f'train:{index}', _context(row), _call_oracle(oracle, _context(row)))
        for index, row in enumerate(_training_cases())
    )
    challenge_contexts = tuple(_context(row) for row in _challenge_cases())
    need = OperatorInventionNeed(
        'external:active-discovery-linear-step',
        ('x', 'a', 'b', 'fa', 'fb'),
        'out',
        constants=(0, 1),
        max_depth=3,
        max_candidates=1000,
    )

    harness_free = synthesize_with_vocabulary(need, train, vocabulary)
    active = discover_verified_subgoal(
        need,
        train,
        challenge_contexts,
        vocabulary,
        lambda context: _call_oracle(oracle, context),
        budget=ProbeBudget(
            max_oracle_calls=900,
            max_interventions=40,
            subgoal_max_depth=2,
            subgoal_max_candidates=12000,
            max_cegis_rounds=2,
        ),
    )

    heldout_exact = 0
    if active.passed and active.full_expression is not None:
        for row in _heldout_cases():
            context = _context(row)
            actual = float(evaluate_with_vocabulary(active.full_expression, context, vocabulary))
            expected = _call_oracle(oracle, context)
            heldout_exact += int(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12))

    passed = bool(
        (not harness_free.passed)
        and active.passed
        and active.challenge_exact == len(challenge_contexts)
        and heldout_exact == len(_heldout_cases())
    )
    return {
        'passed': passed,
        'source_id': str(source_id),
        'source_commit': str(source_commit),
        'source_exposure': 'io_only',
        'manual_probe_rows': 0,
        'probe_field_hints': 0,
        'harness_free_base_passed': bool(harness_free.passed),
        'active_probe_passed': bool(active.passed),
        'active_probe_reason': active.reason,
        'oracle_calls_during_discovery': active.oracle_calls,
        'interventions_considered': active.interventions_considered,
        'exposure_abstraction_id': active.abstraction_id,
        'exposure_target_param_index': active.target_param_index,
        'fixed_field_profile_ids': [list(item) for item in active.fixed_field_profile_ids],
        'fixed_values': [value for _field, value in active.fixed_field_values],
        'challenge_cases': len(challenge_contexts),
        'challenge_exact': active.challenge_exact if active.passed else 0,
        'heldout_cases': len(_heldout_cases()),
        'heldout_exact': heldout_exact,
        'learned_abstraction_digests': learned_digests,
        'subgoal_expression': active.subgoal_expression.to_data() if active.subgoal_expression is not None else None,
        'learned_expression': active.full_expression.to_data() if active.full_expression is not None else None,
        'trainable_parameter_count': 0,
        'claim_boundary': (
            'I/O-only transfer with autonomous bounded intervention discovery; not source induction, '
            'open-ended experiment design, or general program synthesis.'
        ),
    }


if __name__ == '__main__':
    raise SystemExit('Pass an external oracle callable from a hosted verification harness.')
