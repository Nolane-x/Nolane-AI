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


def _run(order: tuple[str, ...], total_budget: int):
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
        composition_max_candidates_per_pair=total_budget,
        max_composition_candidates_total=total_budget,
    )


def _selected_roles(receipt, order: tuple[str, ...]) -> set[str]:
    if receipt.selected is None:
        return set()
    return {
        order[position]
        for spec in receipt.selected.program.interventions
        for position, _value in spec.bindings
    }


def test_global_pair_budget_is_invariant_to_positional_hash_order() -> None:
    # The semantic task is identical. Only field position changes, which changes
    # InterventionSpec hashes and therefore the current profile/pair iteration order.
    # Put the true {left,right} intervention pair first in one schema and last in
    # another. A global search budget must buy equivalent semantic coverage rather
    # than letting early pairs monopolize the entire budget.
    early = ('x', 'right', 'left', 'lo', 'hi', 'middle')
    late = ('right', 'x', 'lo', 'hi', 'left', 'middle')

    roomy_early = _run(early, 120_000)
    roomy_late = _run(late, 120_000)
    assert roomy_early.passed is True
    assert roomy_late.passed is True
    assert _selected_roles(roomy_early, early) == {'left', 'right'}
    assert _selected_roles(roomy_late, late) == {'left', 'right'}

    # Use the actual candidate cost of the causal pair when it is scheduled first.
    # This is enough budget to solve the task semantically; moving the same pair later
    # must not turn that budget into starvation.
    causal_pair_budget = roomy_early.selected.composition_candidates_considered
    assert causal_pair_budget > 0

    tight_early = _run(early, causal_pair_budget)
    tight_late = _run(late, causal_pair_budget)
    assert tight_early.passed is True
    assert _selected_roles(tight_early, early) == {'left', 'right'}
    assert tight_late.passed is True
    assert _selected_roles(tight_late, late) == {'left', 'right'}
