from __future__ import annotations

from collections.abc import Mapping

from benchmarks.kfigg.r267_three_probe_causal_composition import CONFIGS, ROLES
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import synthesize_three_probe_causal_program


def _rows() -> tuple[dict[str, float], ...]:
    return tuple(
        {field: float(value) for field, value in zip(ROLES, values, strict=True)}
        for values in CONFIGS[:24]
    )


def _oracle(row: Mapping[str, object]) -> float:
    return (
        float(row['a']) * float(row['b'])
        + float(row['c']) * float(row['d'])
        + float(row['e']) * float(row['f'])
    )


def test_success_receipt_counts_each_probe_validation_observation_as_one_case() -> None:
    rows = _rows()
    discovery = rows[:12]
    validation = rows[12:18]
    terminal = rows[18:24]
    need = OperatorInventionNeed(
        'R2.67 independent probe receipt accounting',
        ROLES,
        'out',
        constants=(0.0, 2.0),
        max_depth=4,
        max_candidates=50_000,
    )

    receipt = synthesize_three_probe_causal_program(
        _oracle,
        ROLES,
        need,
        discovery,
        validation,
        terminal_contexts=terminal,
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

    assert receipt.passed is True
    assert len(receipt.probe_expressions) == 3
    expected_cases = len(validation) * len(receipt.probe_expressions)
    assert receipt.probe_validation_cases == expected_cases
    assert receipt.probe_validation_exact == expected_cases
    assert receipt.probe_validation_exact <= receipt.probe_validation_cases
