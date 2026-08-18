from __future__ import annotations

from collections.abc import Mapping

from cogcoder.r264_learned_contextual_composition import discover_contextual_composition_structure


_ROLES = ('x', 'lo', 'hi', 'left', 'middle', 'right')


def _band_select(context: Mapping[str, object]) -> float:
    x = float(context['x'])
    lo = float(context['lo'])
    hi = float(context['hi'])
    if x < lo:
        return float(context['left'])
    if x > hi:
        return float(context['right'])
    return float(context['middle'])


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


def _run(order: tuple[str, ...], total_budget: int = 120_000):
    rows = _rows()
    return discover_contextual_composition_structure(
        _band_select,
        order,
        (0.0,),
        rows[:18],
        rows[18:24],
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_pair=12_000,
        max_composition_candidates_total=total_budget,
    )


def _selected_roles(receipt, order: tuple[str, ...]) -> frozenset[str]:
    if receipt.selected is None:
        return frozenset()
    return frozenset(
        order[position]
        for spec in receipt.selected.program.interventions
        for position, _value in spec.bindings
    )


def test_roomy_search_preserves_selected_semantic_roles_across_position_permutations() -> None:
    # Same task, same values, same roomy budget. Only the positional schema changes.
    # R2.66 claims positional invariance, so content-addressed intervention hashes must
    # not change which semantic intervention roles win the deterministic selection.
    order_a = ('x', 'right', 'left', 'lo', 'hi', 'middle')
    order_b = ('right', 'x', 'lo', 'hi', 'left', 'middle')

    a = _run(order_a)
    b = _run(order_b)

    assert a.passed is True
    assert b.passed is True
    roles_a = _selected_roles(a, order_a)
    roles_b = _selected_roles(b, order_b)
    assert roles_a == roles_b, (roles_a, roles_b)
    assert a.false_accepts == 0
    assert b.false_accepts == 0
