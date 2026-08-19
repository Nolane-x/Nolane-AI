from __future__ import annotations

# R2.67.1 triplet-budget fairness contract.
#
# This deliberately does not prescribe a host-selected causal triple.  A roomy
# search first discovers whichever three semantic intervention roles the system
# itself selects.  The same task is then re-expressed under a different field
# position layout and finally rerun with a global budget tightened to the cost of
# the roomy selected composition.  Pass/abstain authority must depend on semantic
# evidence, not caller field positions or incidental intervention enumeration.

from collections.abc import Mapping

from cogcoder.r267_three_probe_causal_composition import discover_three_probe_structure


FIELDS = ('a', 'b', 'c', 'd', 'e', 'f')
BASE_ROWS = (
    (1.0, 2.0, 0.0), (2.0, 3.0, 0.0),
    (1.0, 0.0, 2.0), (2.0, 0.0, 3.0),
    (0.0, 1.0, 2.0), (0.0, 2.0, 3.0),
    (1.0, 2.0, 3.0), (4.0, 2.0, 3.0),
    (2.0, 1.0, 3.0), (2.0, 4.0, 3.0),
    (2.0, 3.0, 1.0), (2.0, 3.0, 4.0),
    (-2.0, 5.0, 3.0), (4.0, -3.0, 2.0),
    (5.0, 2.0, -4.0), (-3.0, -2.0, 6.0),
    (7.0, -1.0, -5.0), (-4.0, 6.0, -2.0),
)


def _rows() -> tuple[dict[str, float], ...]:
    rows: list[dict[str, float]] = []
    for index, (a, b, c) in enumerate(BASE_ROWS):
        # Keep d + 2e + 3f == 0 on every original context, while preserving
        # pairwise-identical distractor values for the authored lower-order
        # collision pairs.  Intervening on d/e/f still yields three distinct,
        # non-degenerate semantic profiles, so the scheduler must consider a
        # genuine multi-triplet frontier rather than the trivial 3-profile case.
        scale = float(index // 2 + 1)
        d = scale
        e = 2.0 * scale
        f = -5.0 * scale / 3.0
        rows.append({'a': a, 'b': b, 'c': c, 'd': d, 'e': e, 'f': f})
    return tuple(rows)


def _oracle(context: Mapping[str, object]) -> float:
    a = float(context['a'])
    b = float(context['b'])
    c = float(context['c'])
    d = float(context['d'])
    e = float(context['e'])
    f = float(context['f'])
    return a * b + b * c + c * a + d + 2.0 * e + 3.0 * f


def _run(order: tuple[str, ...], *, per_triplet_budget: int, total_budget: int):
    rows = _rows()
    return discover_three_probe_structure(
        _oracle,
        order,
        (0.0,),
        rows[:12],
        rows[12:18],
        intervention_arity=1,
        composition_constants=(0.0, 2.0),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=per_triplet_budget,
        max_composition_candidates_total=total_budget,
        ablation_max_candidates=8_000,
        composition_beam_width=128,
    )


def _selected_roles(receipt, order: tuple[str, ...]) -> frozenset[str]:
    if receipt.selected is None:
        return frozenset()
    return frozenset(
        order[position]
        for spec in receipt.selected.interventions
        for position, _value in spec.bindings
    )


def _semantic_outcome(receipt, order: tuple[str, ...]) -> tuple[bool, frozenset[str], str]:
    return receipt.passed, _selected_roles(receipt, order), receipt.reason


def test_roomy_triplet_search_preserves_semantic_roles_across_position_permutations() -> None:
    order_a = ('a', 'd', 'b', 'e', 'c', 'f')
    order_b = ('f', 'c', 'e', 'b', 'd', 'a')
    a = _run(order_a, per_triplet_budget=8_000, total_budget=160_000)
    b = _run(order_b, per_triplet_budget=8_000, total_budget=160_000)
    assert a.passed is True, a.reason
    assert b.passed is True, b.reason
    roles_a = _selected_roles(a, order_a)
    roles_b = _selected_roles(b, order_b)
    assert roles_a == roles_b
    assert len(roles_a) == 3
    assert a.false_accepts == b.false_accepts == 0


def test_tight_global_triplet_budget_has_position_invariant_semantic_outcome() -> None:
    early = ('a', 'd', 'b', 'e', 'c', 'f')
    late = ('f', 'c', 'e', 'b', 'd', 'a')
    roomy_early = _run(early, per_triplet_budget=8_000, total_budget=160_000)
    roomy_late = _run(late, per_triplet_budget=8_000, total_budget=160_000)
    assert roomy_early.passed is True, roomy_early.reason
    assert roomy_late.passed is True, roomy_late.reason
    roomy_roles = _selected_roles(roomy_early, early)
    assert roomy_roles == _selected_roles(roomy_late, late)
    assert len(roomy_roles) == 3

    budget = roomy_early.selected.composition_candidates_considered
    assert 0 < budget <= 8_000
    tight_early = _run(early, per_triplet_budget=budget, total_budget=budget)
    tight_late = _run(late, per_triplet_budget=budget, total_budget=budget)

    assert _semantic_outcome(tight_early, early) == _semantic_outcome(tight_late, late)
    assert tight_early.composition_candidates_considered <= budget
    assert tight_late.composition_candidates_considered <= budget
    assert tight_early.false_accepts == tight_late.false_accepts == 0
