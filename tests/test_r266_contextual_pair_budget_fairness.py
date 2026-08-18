from __future__ import annotations

from collections.abc import Mapping

from cogcoder.r264_learned_contextual_composition import discover_contextual_composition_structure


_ROLES = ('x', 'lo', 'hi', 'left', 'middle', 'right')
_EXPECTED_CAUSAL_ROLES = frozenset({'lo', 'right'})


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


def _run(order: tuple[str, ...], *, per_pair_budget: int, total_budget: int):
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
        composition_max_candidates_per_pair=per_pair_budget,
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
    order_a = ('x', 'right', 'left', 'lo', 'hi', 'middle')
    order_b = ('right', 'x', 'lo', 'hi', 'left', 'middle')

    a = _run(order_a, per_pair_budget=12_000, total_budget=120_000)
    b = _run(order_b, per_pair_budget=12_000, total_budget=120_000)

    assert a.passed is True
    assert b.passed is True
    roles_a = _selected_roles(a, order_a)
    roles_b = _selected_roles(b, order_b)
    assert roles_a == roles_b == _EXPECTED_CAUSAL_ROLES
    assert a.false_accepts == 0
    assert b.false_accepts == 0


def test_global_pair_budget_does_not_starve_same_causal_pair_when_hash_order_moves_it_late() -> None:
    # For one-anchor, arity-1 interventions the content-addressed profile order over
    # six positions is [2, 1, 5, 3, 4, 0].  Therefore a pair bound to positions
    # {2,1} is considered first, while {4,0} is considered last.  These two schemas
    # place the SAME semantic {lo,right} pair at those positions respectively.
    early = ('x', 'right', 'lo', 'left', 'middle', 'hi')
    late = ('right', 'x', 'hi', 'left', 'lo', 'middle')

    roomy_early = _run(early, per_pair_budget=12_000, total_budget=120_000)
    roomy_late = _run(late, per_pair_budget=12_000, total_budget=120_000)
    assert roomy_early.passed is True
    assert roomy_late.passed is True
    assert _selected_roles(roomy_early, early) == _EXPECTED_CAUSAL_ROLES
    assert _selected_roles(roomy_late, late) == _EXPECTED_CAUSAL_ROLES

    # This is the exact synthesis cost of the causal pair when the pair is scheduled
    # first.  It is sufficient semantic search budget for the task.  Repositioning
    # the same pair later must not let unrelated earlier pairs consume all of it.
    causal_pair_budget = roomy_early.selected.composition_candidates_considered
    assert 0 < causal_pair_budget <= 12_000

    tight_early = _run(
        early,
        per_pair_budget=causal_pair_budget,
        total_budget=causal_pair_budget,
    )
    tight_late = _run(
        late,
        per_pair_budget=causal_pair_budget,
        total_budget=causal_pair_budget,
    )

    assert tight_early.passed is True
    assert _selected_roles(tight_early, early) == _EXPECTED_CAUSAL_ROLES
    assert tight_late.passed is True
    assert _selected_roles(tight_late, late) == _EXPECTED_CAUSAL_ROLES
    assert tight_early.false_accepts == 0
    assert tight_late.false_accepts == 0
