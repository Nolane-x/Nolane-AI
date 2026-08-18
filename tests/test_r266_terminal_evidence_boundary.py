import pytest

from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r266_learned_contextual_composition import synthesize_contextual_composition_program


_FIELDS = ('x', 'lo', 'hi', 'left', 'middle', 'right')


def _row(x):
    return {
        'x': float(x),
        'lo': -1.0,
        'hi': 1.0,
        'left': -7.0,
        'middle': 4.0,
        'right': 9.0,
    }


def _need():
    return OperatorInventionNeed(
        'R2.66 terminal evidence boundary',
        _FIELDS,
        'out',
        constants=(0.0,),
        max_depth=2,
        max_candidates=100,
    )


def test_terminal_overlap_with_learning_evidence_fails_before_oracle():
    calls = 0

    def oracle(row):
        nonlocal calls
        calls += 1
        return row['middle']

    discovery = (_row(-3),)
    validation = (_row(0),)
    with pytest.raises(ValueError, match='disjoint'):
        synthesize_contextual_composition_program(
            oracle,
            _FIELDS,
            _need(),
            discovery,
            validation,
            terminal_contexts=discovery,
        )
    assert calls == 0


def test_duplicate_terminal_context_fails_before_oracle():
    calls = 0

    def oracle(row):
        nonlocal calls
        calls += 1
        return row['middle']

    terminal = (_row(3), _row(3))
    with pytest.raises(ValueError, match='unique'):
        synthesize_contextual_composition_program(
            oracle,
            _FIELDS,
            _need(),
            (_row(-3),),
            (_row(0),),
            terminal_contexts=terminal,
        )
    assert calls == 0
