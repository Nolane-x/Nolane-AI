from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import synthesize_three_probe_causal_program


FIELDS = ('a', 'b', 'c')
ROWS = (
    (1.0, 2.0, 0.0), (2.0, 3.0, 0.0),
    (1.0, 0.0, 2.0), (2.0, 0.0, 3.0),
    (0.0, 1.0, 2.0), (0.0, 2.0, 3.0),
    (1.0, 2.0, 3.0), (4.0, 2.0, 3.0),
    (2.0, 1.0, 3.0), (2.0, 4.0, 3.0),
    (2.0, 3.0, 1.0), (2.0, 3.0, 4.0),
    (-2.0, 5.0, 3.0), (4.0, -3.0, 2.0),
    (5.0, 2.0, -4.0), (-3.0, -2.0, 6.0),
    (7.0, -1.0, -5.0), (-4.0, 6.0, -2.0),
    (3.0, 5.0, -2.0), (-5.0, 4.0, 7.0),
    (6.0, -3.0, -4.0), (-7.0, -2.0, 5.0),
    (8.0, 3.0, -6.0), (-6.0, 9.0, 2.0),
)


def _rows() -> tuple[dict[str, float], ...]:
    return tuple(
        {field: float(value) for field, value in zip(FIELDS, row, strict=True)}
        for row in ROWS
    )


def _oracle(row: Mapping[str, object]) -> float:
    a = float(row['a'])
    b = float(row['b'])
    c = float(row['c'])
    return a * b + b * c + c * a


def _need() -> OperatorInventionNeed:
    return OperatorInventionNeed(
        'R2.67.1 cyclic terminal authority',
        FIELDS,
        'out',
        constants=(0.0,),
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
        composition_constants=(0.0,),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=20_000,
        max_composition_candidates_total=20_000,
        ablation_max_candidates=12_000,
        composition_beam_width=128,
        probe_constants=(0.0,),
        probe_max_depth=2,
        probe_max_candidates=20_000,
        probe_beam_width=128,
    )


def _key(row: Mapping[str, object]) -> str:
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


def test_terminal_authority_reobserves_each_selected_intervention_and_fails_nonfinite() -> None:
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


def test_success_receipt_has_exact_end_to_end_oracle_ledger() -> None:
    receipt = _run(_oracle)
    validation_cases = len(_rows()[12:18])
    terminal_cases = len(_rows()[18:24])
    assert receipt.passed is True
    assert len(receipt.probe_expressions) == 3
    assert receipt.probe_validation_cases == validation_cases * 3
    assert receipt.probe_validation_exact == receipt.probe_validation_cases
    assert receipt.terminal_probe_validation_cases == terminal_cases * 3
    assert receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases
    assert receipt.final_validation_cases == terminal_cases
    assert receipt.final_validation_exact == terminal_cases
    assert receipt.oracle_calls_total == receipt.structure.oracle_calls + terminal_cases * 4
