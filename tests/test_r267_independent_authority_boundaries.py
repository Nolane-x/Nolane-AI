from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import synthesize_three_probe_causal_program


FIELDS = ('a', 'b', 'c', 'd', 'e', 'f')
CONFIGS = (
    (-7, -13, 4, -3, -10, -13), (7, 5, -12, 10, -6, 9),
    (-13, 8, 8, -12, 6, -9), (12, 7, 4, 2, -13, -3),
    (-3, -11, 7, 11, 10, -3), (-10, 5, 4, 9, -6, 6),
    (8, -3, 5, 2, -10, 3), (-11, -7, -3, -13, -7, -13),
    (11, 5, -5, -2, 8, 2), (5, -5, 9, 7, -6, -3),
    (12, -5, 11, -4, -2, 10), (-7, 9, 9, -9, -8, -7),
    (11, -10, -5, 11, -9, 4), (13, -8, 2, -6, -5, -12),
    (-5, 8, 11, 8, -9, 13), (10, -10, -9, 6, 12, -2),
    (6, -9, 4, 2, 9, -7), (8, -11, -13, -4, -11, -4),
    (-4, 9, -12, 13, -12, -5), (-10, -13, 10, 11, -10, -7),
    (4, 9, 2, -2, 4, 13), (13, 9, 6, -6, 4, 12),
    (13, -5, -6, 3, -11, 9), (-6, 11, 13, -9, -3, -10),
)


def _rows() -> tuple[dict[str, float], ...]:
    return tuple(
        {field: float(value) for field, value in zip(FIELDS, values, strict=True)}
        for values in CONFIGS
    )


def _oracle(row: Mapping[str, object]) -> float:
    return (
        float(row['a']) * float(row['b'])
        + float(row['c']) * float(row['d'])
        + float(row['e']) * float(row['f'])
    )


def _need() -> OperatorInventionNeed:
    return OperatorInventionNeed(
        'R2.67 independent terminal authority',
        FIELDS,
        'out',
        constants=(0.0, 2.0),
        max_depth=4,
        max_candidates=50_000,
    )


def _run(oracle, *, terminal=None, context_validator=None):
    rows = _rows()
    return synthesize_three_probe_causal_program(
        oracle,
        FIELDS,
        _need(),
        rows[:12],
        rows[12:18],
        terminal_contexts=rows[18:24] if terminal is None else terminal,
        context_validator=context_validator,
        intervention_anchor_values=(0.0,),
        intervention_arity=1,
        composition_constants=(0.0, 2.0),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=35_000,
        max_composition_candidates_total=70_000,
        ablation_max_candidates=20_000,
        composition_beam_width=192,
        probe_constants=(0.0,),
        probe_max_depth=2,
        probe_max_candidates=30_000,
        probe_beam_width=160,
    )


def _key(row: Mapping[str, object]) -> str:
    # Exact JSON is enough to target the same concrete terminal intervention rows;
    # R2.67 itself uses the stronger numeric-semantic key for authority decisions.
    return json.dumps(dict(row), sort_keys=True, separators=(',', ':'), allow_nan=False)


def _selected_terminal_intervention_keys(control) -> set[str]:
    rows = _rows()
    assert control.structure.selected is not None
    return {
        _key(profile.intervention.apply(row, FIELDS))
        for row in rows[18:24]
        for profile in control.structure.selected.profiles
    }


def test_numeric_semantic_alias_cannot_reuse_learning_context_as_terminal_evidence() -> None:
    rows = _rows()
    alias = {
        key: int(value) if float(value).is_integer() else value
        for key, value in rows[0].items()
    }
    with pytest.raises(ValueError, match='disjoint'):
        _run(_oracle, terminal=(alias,))


def test_terminal_authority_reobserves_each_selected_intervention_and_fails_on_nonfinite_output() -> None:
    control = _run(_oracle)
    assert control.passed is True
    targeted = _selected_terminal_intervention_keys(control)
    hits = 0

    def oracle(row: Mapping[str, object]) -> float:
        nonlocal hits
        if _key(row) in targeted:
            hits += 1
            return float('nan')
        return _oracle(row)

    receipt = _run(oracle)
    assert hits > 0
    assert receipt.passed is False
    assert 'terminal' in receipt.reason
    assert receipt.oracle_calls_total > receipt.structure.oracle_calls


def test_terminal_intervention_validator_runs_before_oracle_call() -> None:
    control = _run(_oracle)
    assert control.passed is True
    targeted = _selected_terminal_intervention_keys(control)
    invalid_oracle_calls = 0

    def validator(row: Mapping[str, object]) -> bool:
        return _key(row) not in targeted

    def oracle(row: Mapping[str, object]) -> float:
        nonlocal invalid_oracle_calls
        if _key(row) in targeted:
            invalid_oracle_calls += 1
        return _oracle(row)

    receipt = _run(oracle, context_validator=validator)
    assert receipt.passed is False
    assert 'terminal' in receipt.reason
    assert invalid_oracle_calls == 0


def test_success_receipt_has_exact_end_to_end_terminal_oracle_ledger() -> None:
    receipt = _run(_oracle)
    terminal_cases = len(_rows()[18:24])
    assert receipt.passed is True
    assert receipt.terminal_probe_validation_cases == terminal_cases * 3
    assert receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases
    assert receipt.final_validation_cases == terminal_cases
    assert receipt.final_validation_exact == terminal_cases
    assert receipt.oracle_calls_total == receipt.structure.oracle_calls + terminal_cases * 4
