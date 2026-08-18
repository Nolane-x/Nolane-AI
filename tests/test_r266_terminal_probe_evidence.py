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
                'x': x,
                'lo': lo,
                'hi': hi,
                'left': left,
                'middle': middle,
                'right': right,
            })
    return tuple(rows)


def _key(row: Mapping[str, object]) -> str:
    return json.dumps(dict(row), sort_keys=True, separators=(',', ':'), allow_nan=False)


def _apply(row: Mapping[str, object], bindings: tuple[tuple[int, object], ...]) -> dict[str, object]:
    changed = dict(row)
    for position, value in bindings:
        changed[FIELDS[position]] = value
    return changed


def _need(label: str) -> OperatorInventionNeed:
    return OperatorInventionNeed(
        label,
        FIELDS,
        'out',
        constants=(0.0,),
        max_depth=3,
        max_candidates=25_000,
    )


def _run(oracle, discovery, validation, terminal):
    return synthesize_contextual_composition_program(
        oracle,
        FIELDS,
        _need('R2.66 independent terminal selected-probe evidence'),
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


def test_terminal_authority_rechecks_selected_intervention_outputs_not_only_final_expression() -> None:
    rows = _rows()
    discovery = rows[:18]
    validation = rows[18:24]
    terminal = rows[24:30]

    # First freeze the exact causal pair selected by the normal oracle. This prevents
    # a future implementation from satisfying the challenger by querying an unrelated
    # terminal intervention while leaving the two selected learned probes untested.
    control = _run(_band_select, discovery, validation, terminal)
    assert control.passed is True
    assert control.structure.selected is not None
    assert len(control.probe_expressions) == 2
    selected_interventions = (
        control.structure.selected.left_profile.intervention,
        control.structure.selected.right_profile.intervention,
    )

    learning_query_keys: set[str] = set()
    for row in discovery + validation:
        learning_query_keys.add(_key(row))
        for intervention in selected_interventions:
            learning_query_keys.add(_key(_apply(row, intervention.bindings)))

    terminal_original_keys = {_key(row) for row in terminal}
    selected_terminal_query_keys = {
        _key(_apply(row, intervention.bindings))
        for row in terminal
        for intervention in selected_interventions
    } - learning_query_keys - terminal_original_keys
    assert selected_terminal_query_keys

    calls = 0
    selected_terminal_intervention_calls = 0

    def oracle(row: Mapping[str, object]) -> float:
        nonlocal calls, selected_terminal_intervention_calls
        calls += 1
        if _key(row) in selected_terminal_query_keys:
            selected_terminal_intervention_calls += 1
            return float('nan')
        return _band_select(row)

    receipt = _run(oracle, discovery, validation, terminal)

    # A terminally verified causal composition must independently re-observe the
    # selected interventions and validate the two learned probe expressions before
    # granting authority to the final composition.
    assert selected_terminal_intervention_calls > 0
    assert receipt.passed is False
    assert 'terminal' in receipt.reason
    assert calls > receipt.structure.oracle_calls
