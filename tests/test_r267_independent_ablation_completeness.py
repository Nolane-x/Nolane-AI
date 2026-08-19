from __future__ import annotations

from collections.abc import Mapping

from cogcoder.r267_three_probe_causal_composition import discover_three_probe_structure


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
)


def _rows() -> tuple[dict[str, float], ...]:
    return tuple(
        {field: float(value) for field, value in zip(FIELDS, values, strict=True)}
        for values in CONFIGS
    )


def _tri_bilinear(row: Mapping[str, object]) -> float:
    return (
        float(row['a']) * float(row['b'])
        + float(row['c']) * float(row['d'])
        + float(row['e']) * float(row['f'])
    )


def test_budget_exhausted_lower_order_search_is_not_causal_falsification() -> None:
    rows = _rows()
    receipt = discover_three_probe_structure(
        _tri_bilinear,
        FIELDS,
        (0.0,),
        rows[:12],
        rows[12:18],
        intervention_arity=1,
        composition_constants=(0.0, 2.0),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=35_000,
        max_composition_candidates_total=70_000,
        ablation_max_candidates=1,
        composition_beam_width=192,
    )

    assert receipt.passed is False
    assert receipt.selected is None
    assert receipt.false_accepts == 0
    assert receipt.reason in {
        'ablation_search_inconclusive',
        'ablation_budget_exhausted',
    }
