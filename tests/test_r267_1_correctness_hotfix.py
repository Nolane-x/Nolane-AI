from __future__ import annotations

from collections.abc import Mapping

import cogcoder.r267_three_probe_causal_composition as r267
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import (
    discover_three_probe_structure,
    synthesize_three_probe_causal_program,
)


CYCLIC_FIELDS = ('a', 'b', 'c')
CYCLIC_ROWS = (
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

TRI_FIELDS = ('a', 'b', 'c', 'd', 'e', 'f')
TRI_ROWS = (
    (-7, -13, 4, -3, -10, -13), (7, 5, -12, 10, -6, 9),
    (-13, 8, 8, -12, 6, -9), (12, 7, 4, 2, -13, -3),
    (-3, -11, 7, 11, 10, -3), (-10, 5, 4, 9, -6, 6),
    (8, -3, 5, 2, -10, 3), (-11, -7, -3, -13, -7, -13),
    (11, 5, -5, -2, 8, 2), (5, -5, 9, 7, -6, -3),
    (12, -5, 11, -4, -2, 10), (-7, 9, 9, -9, -8, -7),
    (11, -10, -5, 11, -9, 4), (13, -8, 2, -6, -5, -12),
    (-5, 8, 11, 8, -9, 13), (10, -10, -9, 6, 12, -2),
    (6, -9, 4, 2, 9, -7), (8, -11, -13, -4, -11, -4),
)


def _rows(fields: tuple[str, ...], values) -> tuple[dict[str, float], ...]:
    return tuple(
        {field: float(value) for field, value in zip(fields, row, strict=True)}
        for row in values
    )


def _cyclic_oracle(row: Mapping[str, object]) -> float:
    a = float(row['a'])
    b = float(row['b'])
    c = float(row['c'])
    return a * b + b * c + c * a


def _tri_oracle(row: Mapping[str, object]) -> float:
    return (
        float(row['a']) * float(row['b'])
        + float(row['c']) * float(row['d'])
        + float(row['e']) * float(row['f'])
    )


def _tri_discovery():
    rows = _rows(TRI_FIELDS, TRI_ROWS)
    return discover_three_probe_structure(
        _tri_oracle,
        TRI_FIELDS,
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


def test_probe_validation_receipt_uses_probe_observation_case_units() -> None:
    rows = _rows(CYCLIC_FIELDS, CYCLIC_ROWS)
    need = OperatorInventionNeed(
        'R2.67.1 corrected cyclic receipt accounting',
        CYCLIC_FIELDS,
        'out',
        constants=(0.0,),
        max_depth=4,
        max_candidates=50_000,
    )
    receipt = synthesize_three_probe_causal_program(
        _cyclic_oracle,
        CYCLIC_FIELDS,
        need,
        rows[:12],
        rows[12:18],
        terminal_contexts=rows[18:24],
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
    assert receipt.passed is True
    assert len(receipt.probe_expressions) == 3
    expected_cases = 6 * 3
    assert receipt.probe_validation_cases == expected_cases
    assert receipt.probe_validation_exact == expected_cases
    assert receipt.probe_validation_exact <= receipt.probe_validation_cases


def test_old_tri_bilinear_family_fails_closed_without_a_lower_order_certificate() -> None:
    structure = _tri_discovery()
    assert structure.passed is False
    assert structure.selected is None
    assert structure.false_accepts == 0
    assert structure.reason == 'ablation_search_inconclusive'


def test_pair_ablation_search_receives_fields_free_under_that_pair(monkeypatch) -> None:
    # The original R2.67 union mask exposed only three original fields to every
    # pair ablation.  With two distinct one-field interventions, a genuine pair
    # must instead receive four original fields plus __p0/__p1.
    real_search = r267._synthesize_r267_expression
    real_collision = r267._examples_have_target_collision
    pair_field_sets: list[tuple[str, ...]] = []

    def collision_gate(examples):
        names = set(examples[0].context)
        if '__p0' in names and '__p1' not in names:
            return True  # certify singleton insufficiency so the pair stage runs
        return real_collision(examples)

    def traced_search(field_names, constants, examples, *, max_depth, max_candidates, beam_width):
        names = tuple(map(str, field_names))
        if '__p0' in names and '__p1' in names and '__p2' not in names:
            pair_field_sets.append(names)
        return real_search(
            field_names,
            constants,
            examples,
            max_depth=max_depth,
            max_candidates=max_candidates,
            beam_width=beam_width,
        )

    monkeypatch.setattr(r267, '_examples_have_target_collision', collision_gate)
    monkeypatch.setattr(r267, '_synthesize_r267_expression', traced_search)
    structure = _tri_discovery()

    assert pair_field_sets
    assert all(len(names) == 6 for names in pair_field_sets)
    assert all(sum(not name.startswith('__p') for name in names) == 4 for names in pair_field_sets)
    assert structure.passed is False
    assert structure.selected is None
