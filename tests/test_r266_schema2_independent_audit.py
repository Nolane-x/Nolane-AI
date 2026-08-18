from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from cogcoder._r266_contextual_composition_core import (
    ContextualInterventionProfile,
    _profile_semantic_id,
)
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r258_intervention_discovery import InterventionSpec
from cogcoder.r266_learned_contextual_composition import synthesize_contextual_composition_program


FIELDS = ('x', 'lo', 'hi', 'left', 'middle', 'right')


def _band_select(row: Mapping[str, object]) -> float:
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
        (-30.0, -20.0, -71.0, 41.0, -51.0),
        (-10.0, 40.0, 61.0, -31.0, 91.0),
        (-50.0, 10.0, -81.0, 51.0, 21.0),
        (10.0, 60.0, 31.0, -61.0, -41.0),
        (-40.0, 30.0, 81.0, 21.0, -91.0),
        (-20.0, 50.0, -61.0, -11.0, 71.0),
    )
    rows: list[dict[str, float]] = []
    for lo, hi, left, middle, right in configs:
        for x in (lo - 7.0, lo, (lo + hi) / 2.0, hi, hi + 7.0):
            rows.append({'x': x, 'lo': lo, 'hi': hi, 'left': left, 'middle': middle, 'right': right})
    return tuple(rows)


def _need(label: str) -> OperatorInventionNeed:
    return OperatorInventionNeed(label, FIELDS, 'out', constants=(0.0,), max_depth=3, max_candidates=25_000)


def _synthesize(oracle, terminal):
    rows = _rows()
    return synthesize_contextual_composition_program(
        oracle,
        FIELDS,
        _need('R2.66 schema2 independent audit'),
        rows[:18],
        rows[18:24],
        terminal_contexts=terminal,
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_pair=12_000,
        max_composition_candidates_total=120_000,
        probe_constants=(0.0,),
        probe_max_depth=3,
        probe_max_candidates=20_000,
    )


def _key(row: Mapping[str, object]) -> str:
    return json.dumps(dict(row), sort_keys=True, separators=(',', ':'), allow_nan=False)


def _zero_interventions(rows: tuple[dict[str, float], ...]) -> set[str]:
    out: set[str] = set()
    for row in rows:
        for field in FIELDS:
            changed = dict(row)
            changed[field] = 0.0
            if changed != row:
                out.add(_key(changed))
    return out


def test_terminal_numeric_semantic_alias_is_rejected() -> None:
    rows = _rows()
    alias = {key: int(value) for key, value in rows[0].items()}
    with pytest.raises(ValueError, match='disjoint'):
        _synthesize(_band_select, (alias,))


def test_terminal_cannot_reuse_an_intervention_profile_oracle_input() -> None:
    rows = _rows()
    alias = dict(rows[0])
    alias['middle'] = 0.0
    assert alias not in rows[:24]
    with pytest.raises(ValueError, match='disjoint'):
        _synthesize(_band_select, (alias,))


def test_public_receipt_exposes_exact_total_oracle_ledger() -> None:
    rows = _rows()
    calls = 0

    def oracle(row: Mapping[str, object]) -> float:
        nonlocal calls
        calls += 1
        return _band_select(row)

    receipt = _synthesize(oracle, rows[24:30])
    assert receipt.passed is True
    assert getattr(receipt, 'oracle_calls_total', None) == calls
    assert calls >= receipt.structure.oracle_calls + len(rows[24:30])


def test_profile_semantic_identity_normalizes_numeric_equivalence() -> None:
    spec = InterventionSpec(((0, 0.0),))
    integerish = ContextualInterventionProfile(spec, (1, 2, 0.0), (3, -0.0))
    floatish = ContextualInterventionProfile(spec, (1.0, 2.0, -0.0), (3.0, 0.0))
    assert _profile_semantic_id(integerish) == _profile_semantic_id(floatish)


def test_terminal_authority_rechecks_selected_intervention_probe_evidence() -> None:
    rows = _rows()
    discovery = rows[:18]
    validation = rows[18:24]
    terminal = rows[24:30]
    learning_query_keys = _zero_interventions(discovery + validation)
    terminal_original_keys = {_key(row) for row in terminal}
    fail_keys = _zero_interventions(terminal) - learning_query_keys - terminal_original_keys
    assert fail_keys

    terminal_intervention_calls = 0

    def oracle(row: Mapping[str, object]) -> float:
        nonlocal terminal_intervention_calls
        if _key(row) in fail_keys:
            terminal_intervention_calls += 1
            return float('nan')
        return _band_select(row)

    receipt = _synthesize(oracle, terminal)
    assert terminal_intervention_calls > 0
    assert receipt.passed is False
    assert 'terminal' in receipt.reason
