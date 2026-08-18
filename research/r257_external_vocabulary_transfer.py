from __future__ import annotations

import math
from typing import Callable

from benchmarks.kfigg.r257_verified_vocabulary_growth import build_promoted_vocabulary
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r257_vocabulary import evaluate_with_vocabulary
from cogcoder.r257_vocabulary_synthesis import synthesize_base_with_budget, synthesize_with_vocabulary


def _call_oracle(oracle: Callable[..., object], x: float, a: float, b: float, fa: float, fb: float) -> float:
    value = float(oracle(x, a, b, fa, fb))
    if not math.isfinite(value):
        raise ValueError('external oracle returned non-finite value')
    return value


def _probe_rows(oracle: Callable[..., object]) -> tuple[OperatorExample, ...]:
    rows = []
    cases = (
        (-4.0, 0.0, 8.0), (0.0, 0.0, 8.0), (2.0, 0.0, 8.0), (4.0, 0.0, 8.0),
        (6.0, 0.0, 8.0), (8.0, 0.0, 8.0), (12.0, 0.0, 8.0),
        (-6.0, -4.0, 4.0), (0.0, -4.0, 4.0), (6.0, -4.0, 4.0),
    )
    for i, (x, a, b) in enumerate(cases):
        rows.append(OperatorExample(f'probe:{i}', {'x': x, 'a': a, 'b': b}, _call_oracle(oracle, x, a, b, 0.0, 1.0)))
    return tuple(rows)


def _full_rows(oracle: Callable[..., object], cases: tuple[tuple[float, float, float, float, float], ...], prefix: str) -> tuple[OperatorExample, ...]:
    return tuple(
        OperatorExample(
            f'{prefix}:{i}',
            {'x': x, 'a': a, 'b': b, 'fa': fa, 'fb': fb},
            _call_oracle(oracle, x, a, b, fa, fb),
        )
        for i, (x, a, b, fa, fb) in enumerate(cases)
    )


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

    # Active information acquisition: fix endpoint outputs to 0 and 1 so the I/O oracle
    # exposes the latent progress variable without exposing source or implementation text.
    probe_need = OperatorInventionNeed(
        'external:discover-latent-progress', ('x', 'a', 'b'), 'progress',
        constants=(0, 1), max_depth=2, max_candidates=12000,
    )
    probe_rows = _probe_rows(oracle)
    probe_base = synthesize_base_with_budget(probe_need, probe_rows)
    probe_extended = synthesize_with_vocabulary(probe_need, probe_rows, vocabulary)
    if not probe_extended.passed or probe_extended.expression is None:
        return {
            'passed': False, 'source_id': source_id, 'source_commit': source_commit,
            'source_exposure': 'io_only', 'reason': 'latent_progress_not_synthesized',
            'base_passed': False, 'extended_passed': False,
            'challenge_cases': 0, 'challenge_exact': 0, 'heldout_cases': 0, 'heldout_exact': 0,
            'learned_abstraction_digests': learned_digests, 'trainable_parameter_count': 0,
        }

    full_need = OperatorInventionNeed(
        'external:compose-linear-step', ('x', 'a', 'b', 'fa', 'fb'), 'out',
        constants=(0, 1), max_depth=3, max_candidates=1000,
    )
    train_rows = _full_rows(oracle, _training_cases(), 'train')
    base = synthesize_base_with_budget(full_need, train_rows)
    extended = synthesize_with_vocabulary(
        full_need, train_rows, vocabulary, seed_expressions=(probe_extended.expression,),
    )
    challenge = _full_rows(oracle, _challenge_cases(), 'challenge')
    heldout = _full_rows(oracle, _heldout_cases(), 'heldout')
    challenge_exact = 0
    heldout_exact = 0
    if extended.passed and extended.expression is not None:
        for row in challenge:
            actual = float(evaluate_with_vocabulary(extended.expression, row.context, vocabulary))
            challenge_exact += int(math.isclose(actual, float(row.expected), rel_tol=1e-12, abs_tol=1e-12))
        for row in heldout:
            actual = float(evaluate_with_vocabulary(extended.expression, row.context, vocabulary))
            heldout_exact += int(math.isclose(actual, float(row.expected), rel_tol=1e-12, abs_tol=1e-12))

    passed = bool(
        (not probe_base.passed)
        and probe_extended.passed
        and (not base.passed)
        and extended.passed
        and challenge_exact == len(challenge)
        and heldout_exact == len(heldout)
    )
    return {
        'passed': passed,
        'source_id': str(source_id),
        'source_commit': str(source_commit),
        'source_exposure': 'io_only',
        'base_passed': bool(base.passed),
        'extended_passed': bool(extended.passed),
        'probe_base_passed': bool(probe_base.passed),
        'probe_extended_passed': bool(probe_extended.passed),
        'probe_candidates_considered': probe_extended.candidates_considered,
        'full_candidates_considered': extended.candidates_considered,
        'challenge_cases': len(challenge),
        'challenge_exact': challenge_exact,
        'heldout_cases': len(heldout),
        'heldout_exact': heldout_exact,
        'learned_abstraction_digests': learned_digests,
        'learned_expression': extended.expression.to_data() if extended.expression is not None else None,
        'trainable_parameter_count': 0,
        'claim_boundary': 'I/O-only transfer to one independently sourced pure numeric oracle; not source induction or general program synthesis.',
    }


if __name__ == '__main__':
    raise SystemExit('Pass an external oracle callable from a hosted verification harness.')
