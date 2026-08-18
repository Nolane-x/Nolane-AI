from __future__ import annotations

from collections.abc import Mapping

from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import (
    ThreeProbeCompositionReceipt,
    discover_three_probe_structure,
    synthesize_three_probe_causal_program,
)


FIELDS = ('a', 'b', 'c', 'd', 'e', 'f')
CONFIGS = (
    (-7, -13, 4, -3, -10, -13),
    (7, 5, -12, 10, -6, 9),
    (-13, 8, 8, -12, 6, -9),
    (12, 7, 4, 2, -13, -3),
    (-3, -11, 7, 11, 10, -3),
    (-10, 5, 4, 9, -6, 6),
    (8, -3, 5, 2, -10, 3),
    (-11, -7, -3, -13, -7, -13),
    (11, 5, -5, -2, 8, 2),
    (5, -5, 9, 7, -6, -3),
    (12, -5, 11, -4, -2, 10),
    (-7, 9, 9, -9, -8, -7),
    (11, -10, -5, 11, -9, 4),
    (13, -8, 2, -6, -5, -12),
    (-5, 8, 11, 8, -9, 13),
    (10, -10, -9, 6, 12, -2),
    (6, -9, 4, 2, 9, -7),
    (8, -11, -13, -4, -11, -4),
    (-4, 9, -12, 13, -12, -5),
    (-10, -13, 10, 11, -10, -7),
    (4, 9, 2, -2, 4, 13),
    (13, 9, 6, -6, 4, 12),
    (13, -5, -6, 3, -11, 9),
    (-6, 11, 13, -9, -3, -10),
    (9, -6, -11, -7, -6, -8),
    (8, 11, 11, 10, -11, 10),
    (9, -11, 12, 4, -2, -10),
    (4, -11, -5, 10, 13, 6),
    (3, 6, 3, -6, 2, 13),
    (5, 4, 7, -2, -7, 3),
)


def _rows() -> tuple[dict[str, float], ...]:
    return tuple(
        {field: float(value) for field, value in zip(FIELDS, values, strict=True)}
        for values in CONFIGS
    )


def tri_bilinear(row: Mapping[str, object]) -> float:
    return (
        float(row['a']) * float(row['b'])
        + float(row['c']) * float(row['d'])
        + float(row['e']) * float(row['f'])
    )


def _need() -> OperatorInventionNeed:
    return OperatorInventionNeed(
        'R2.67 tri-bilinear three-probe program',
        FIELDS,
        'out',
        constants=(0.0, 2.0),
        max_depth=4,
        max_candidates=50_000,
    )


def _discover(order: tuple[str, ...] = FIELDS):
    rows = _rows()
    return discover_three_probe_structure(
        tri_bilinear,
        order,
        (0.0,),
        rows[:12],
        rows[12:18],
        intervention_arity=1,
        composition_constants=(0.0, 2.0),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=35_000,
        max_composition_candidates_total=70_000,
        ablation_max_candidates=20_000,
        composition_beam_width=192,
    )


def _structure_diagnostics(receipt) -> tuple[object, ...]:
    return (
        receipt.reason,
        receipt.legal_interventions,
        receipt.semantic_profiles,
        receipt.triplets_considered,
        receipt.composition_candidates_considered,
        receipt.singleton_candidates_considered,
        receipt.pair_candidates_considered,
        receipt.oracle_calls,
    )


def test_r267_public_three_probe_api_exists_on_exact_r266_parent() -> None:
    assert callable(discover_three_probe_structure)
    assert callable(synthesize_three_probe_causal_program)
    assert ThreeProbeCompositionReceipt.__name__ == 'ThreeProbeCompositionReceipt'
    assert _need().field_names == FIELDS


def test_authored_tri_bilinear_family_requires_and_discovers_three_probe_composition() -> None:
    receipt = _discover()
    assert receipt.passed is True, _structure_diagnostics(receipt)
    assert receipt.selected is not None
    selected = receipt.selected
    assert len(selected.profiles) == 3
    assert len(set(selected.semantic_profile_ids)) == 3
    assert {'__p0', '__p1', '__p2'} <= set(selected.used_fields)
    assert selected.singleton_ablation_passed == (False, False, False)
    assert selected.pair_ablation_passed == (False, False, False)
    assert receipt.false_accepts == 0
    assert receipt.trainable_parameter_count == 0


def test_full_program_synthesizes_three_executable_probes_and_terminally_reobserves_them() -> None:
    rows = _rows()
    discovery = rows[:12]
    validation = rows[12:18]
    terminal = rows[18:24]
    receipt = synthesize_three_probe_causal_program(
        tri_bilinear,
        FIELDS,
        _need(),
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
    assert receipt.passed is True, (receipt.reason, _structure_diagnostics(receipt.structure))
    assert receipt.expression is not None
    assert len(receipt.probe_expressions) == 3
    assert receipt.probe_validation_cases == len(validation)
    assert receipt.probe_validation_exact == len(validation) * 3
    assert receipt.terminal_probe_validation_cases == len(terminal) * 3
    assert receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases
    assert receipt.final_validation_cases == len(terminal)
    assert receipt.final_validation_exact == len(terminal)
    assert receipt.oracle_calls_total == receipt.structure.oracle_calls + len(terminal) * 4
    assert receipt.trainable_parameter_count == 0
