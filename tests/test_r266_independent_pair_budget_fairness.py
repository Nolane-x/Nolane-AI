from __future__ import annotations

from collections.abc import Mapping

from cogcoder.r266_learned_contextual_composition import discover_contextual_composition_structure


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
    projected = tuple({name: row[name] for name in order} for row in rows)
    return discover_contextual_composition_structure(
        _band_select,
        order,
        (0.0,),
        projected[:18],
        projected[18:24],
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


def _semantic_outcome(receipt, order: tuple[str, ...]) -> tuple[bool, frozenset[str], str]:
    return receipt.passed, _selected_roles(receipt, order), receipt.reason


def test_roomy_control_preserves_semantic_pair_across_position_layouts() -> None:
    early = ('x', 'right', 'lo', 'left', 'middle', 'hi')
    late = ('right', 'x', 'hi', 'left', 'lo', 'middle')
    a = _run(early, per_pair_budget=12_000, total_budget=120_000)
    b = _run(late, per_pair_budget=12_000, total_budget=120_000)
    assert a.passed is True
    assert b.passed is True
    assert _selected_roles(a, early) == _selected_roles(b, late) == _EXPECTED_CAUSAL_ROLES
    assert a.false_accepts == b.false_accepts == 0


def test_tight_global_budget_is_semantically_order_invariant() -> None:
    # Same semantic {lo,right} pair, but its positional intervention hashes place it
    # early in one layout and late in the other. A hard-cap scheduler may solve both
    # or conservatively abstain on both. Positional/hash scheduling alone must not
    # decide pass versus abstain.
    early = ('x', 'right', 'lo', 'left', 'middle', 'hi')
    late = ('right', 'x', 'hi', 'left', 'lo', 'middle')

    roomy = _run(early, per_pair_budget=12_000, total_budget=120_000)
    assert roomy.passed is True
    budget = roomy.selected.composition_candidates_considered
    assert 0 < budget <= 12_000

    a = _run(early, per_pair_budget=budget, total_budget=budget)
    b = _run(late, per_pair_budget=budget, total_budget=budget)

    assert _semantic_outcome(a, early) == _semantic_outcome(b, late)
    assert a.composition_candidates_considered <= budget
    assert b.composition_candidates_considered <= budget
    assert a.false_accepts == b.false_accepts == 0
