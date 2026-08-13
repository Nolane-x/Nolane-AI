from __future__ import annotations

import pytest

from benchmarks.frontier100b.harness import (
    score_arc_exact,
    score_closed_answer,
    validate_comparison_record,
)


def test_arc_exact_accepts_one_of_two_exact_predictions_only():
    target = [[1, 0], [0, 1]]
    assert score_arc_exact([[[0, 0], [0, 0]], target], target) == 1
    assert score_arc_exact([[[1, 0], [1, 0]]], target) == 0
    assert score_arc_exact([[[1, 0], [0, 1, 2]]], target) == 0


def test_closed_answer_normalization_is_conservative():
    assert score_closed_answer('  Paris\n', 'paris')
    assert score_closed_answer('A   B', 'a b')
    assert not score_closed_answer('1/2', '0.5')
    assert not score_closed_answer('approximately 3', '3')


def test_gt100b_hard_claim_requires_a_real_named_reference_run():
    base = {
        'suite': 'frontier100b-v1',
        'locked_protocol_sha256': 'a' * 64,
        'hard_for_gt100b': True,
        'reference_runs': [],
    }
    with pytest.raises(ValueError, match='evaluated >100B reference'):
        validate_comparison_record(base)

    too_small = dict(base)
    too_small['reference_runs'] = [{
        'model': 'example-70b',
        'parameter_count': 70_000_000_000,
        'evaluated': True,
        'score': 0.2,
        'budget': {'tokens': 1000},
    }]
    with pytest.raises(ValueError, match='evaluated >100B reference'):
        validate_comparison_record(too_small)

    valid = dict(base)
    valid['reference_runs'] = [{
        'model': 'named-reference-120b',
        'parameter_count': 120_000_000_000,
        'evaluated': True,
        'score': 0.2,
        'budget': {'tokens': 1000},
    }]
    assert validate_comparison_record(valid)['hard_for_gt100b'] is True
