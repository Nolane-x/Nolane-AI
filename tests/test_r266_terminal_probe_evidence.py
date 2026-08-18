from __future__ import annotations

import json
from collections.abc import Mapping

from cogcoder.r256_operator_invention import OperatorInventionNeed
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
            rows.append({
                'x': x, 'lo': lo, 'hi': hi,
                'left': left, 'middle': middle, 'right': right,
            })
    return tuple(rows)


def _key(row: Mapping[str, object]) -> str:
    return json.dumps(dict(row), sort_keys=True, separators=(',', ':'), allow_nan=False)


def _one_field_zero_interventions(rows: tuple[dict[str, float], ...]) -> set[str]:
    keys: set[str] = set()
    for row in rows:
        for field in FIELDS:
            changed = dict(row)
            changed[field] = 0.0
            if changed != row:
                keys.add(_key(changed))
    return keys


def test_terminal_authority_rechecks_selected_intervention_outputs_not_only_final_expression() -> None:
    rows = _rows()
    discovery = rows[:18]
    validation = rows[18:24]
    terminal = rows[24:30]
    learning_query_keys = _one_field_zero_interventions(discovery + validation)
    terminal_original_keys = {_key(row) for row in terminal}
    terminal_intervention_keys = _one_field_zero_interventions(terminal) - learning_query_keys - terminal_original_keys
    assert terminal_intervention_keys

    calls = 0
    terminal_intervention_calls = 0

    def oracle(row: Mapping[str, object]) -> float:
        nonlocal calls, terminal_intervention_calls
        calls += 1
        if _key(row) in terminal_intervention_keys:
            terminal_intervention_calls += 1
            return float('nan')
        return _band_select(row)

    need = OperatorInventionNeed(
        'R2.66 independent terminal intervention evidence',
        FIELDS,
        'out',
        constants=(0.0,),
        max_depth=3,
        max_candidates=25_000,
    )
    receipt = synthesize_contextual_composition_program(
        oracle,
        FIELDS,
        need,
        discovery,
        validation,
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

    assert terminal_intervention_calls > 0
    assert receipt.passed is False
    assert 'terminal' in receipt.reason
    assert calls > receipt.structure.oracle_calls
