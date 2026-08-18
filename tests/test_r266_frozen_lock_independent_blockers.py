from __future__ import annotations

from collections.abc import Mapping

import pytest

from cogcoder._r266_contextual_composition_core import (
    ContextualInterventionProfile,
    _profile_semantic_id,
)
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r258_intervention_discovery import InterventionSpec
from cogcoder.r266_learned_contextual_composition import (
    discover_contextual_composition_structure,
    synthesize_contextual_composition_program,
)


FIELDS = ('x', 'lo', 'hi', 'left', 'middle', 'right')


def _oracle(row: Mapping[str, object]) -> float:
    x = float(row['x'])
    lo = float(row['lo'])
    hi = float(row['hi'])
    if x < lo:
        return float(row['left'])
    if x > hi:
        return float(row['right'])
    return float(row['middle'])


def _rows() -> tuple[dict[str, float], ...]:
    configs = (
        (-3.0, 2.0, -7.0, 4.0, -5.0),
        (-1.0, 4.0, 6.0, -3.0, 9.0),
        (-5.0, 1.0, -8.0, 5.0, 2.0),
        (0.0, 6.0, 3.0, -6.0, -4.0),
        (-4.0, 3.0, 8.0, 2.0, -9.0),
        (-2.0, 5.0, -6.0, -1.0, 7.0),
    )
    rows: list[dict[str, float]] = []
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


def _need(label: str) -> OperatorInventionNeed:
    return OperatorInventionNeed(
        label,
        FIELDS,
        'out',
        constants=(0.0,),
        max_depth=3,
        max_candidates=25_000,
    )


def _synthesize(oracle, terminal_contexts):
    rows = _rows()
    return synthesize_contextual_composition_program(
        oracle,
        FIELDS,
        _need('R2.66 frozen-lock audit'),
        rows[:18],
        rows[18:24],
        terminal_contexts=terminal_contexts,
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_pair=12_000,
        max_composition_candidates_total=120_000,
        probe_constants=(0.0,),
        probe_max_depth=3,
        probe_max_candidates=20_000,
    )


def test_frozen_core_fails_closed_on_intervention_oracle_error() -> None:
    rows = _rows()
    calls = 0
    failures = 0

    def oracle(row: Mapping[str, object]) -> float:
        nonlocal calls, failures
        calls += 1
        if float(row['middle']) == 0.0:
            failures += 1
            return float('nan')
        return _oracle(row)

    receipt = discover_contextual_composition_structure(
        oracle,
        FIELDS,
        (0.0,),
        rows[:18],
        rows[18:24],
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_pair=12_000,
        max_composition_candidates_total=120_000,
    )
    assert failures > 0
    assert receipt.oracle_calls == calls
    assert receipt.passed is False
    assert receipt.selected is None
    assert receipt.reason.startswith('oracle_error:')
    assert receipt.false_accepts == 0


def test_frozen_terminal_disjointness_is_numeric_semantic_not_json_lexical() -> None:
    rows = _rows()
    alias = {key: int(value) for key, value in rows[0].items()}
    with pytest.raises(ValueError, match='disjoint'):
        _synthesize(_oracle, (alias,))


def test_frozen_terminal_disjointness_includes_intervention_query_inputs() -> None:
    rows = _rows()
    alias = dict(rows[0])
    alias['middle'] = 0.0
    assert alias not in rows[:24]
    with pytest.raises(ValueError, match='disjoint'):
        _synthesize(_oracle, (alias,))


def test_frozen_public_receipt_accounts_for_all_oracle_calls() -> None:
    rows = _rows()
    calls = 0

    def oracle(row: Mapping[str, object]) -> float:
        nonlocal calls
        calls += 1
        return _oracle(row)

    receipt = _synthesize(oracle, rows[24:30])
    assert receipt.passed is True
    assert getattr(receipt, 'oracle_calls_total', None) == calls
    assert calls >= receipt.structure.oracle_calls + 6


def test_profile_semantic_identity_normalizes_numeric_equivalence() -> None:
    spec = InterventionSpec(((0, 0.0),))
    integerish = ContextualInterventionProfile(spec, (1, 2, 0.0), (3, -0.0))
    floatish = ContextualInterventionProfile(spec, (1.0, 2.0, -0.0), (3.0, 0.0))
    assert _profile_semantic_id(integerish) == _profile_semantic_id(floatish)
