from __future__ import annotations

from collections.abc import Mapping

from cogcoder.r267_three_probe_causal_composition import discover_three_probe_structure


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
)


def _contexts() -> tuple[dict[str, float], ...]:
    return tuple({'a': a, 'b': b, 'c': c} for a, b, c in ROWS)


def _oracle(row: Mapping[str, object]) -> float:
    a = float(row['a'])
    b = float(row['b'])
    c = float(row['c'])
    return a * b + b * c + c * a


def _run(order: tuple[str, ...], budget: int):
    rows = _contexts()
    return discover_three_probe_structure(
        _oracle,
        order,
        # Two anchors create six single-field profiles and twenty candidate
        # triplets, so this actually exercises the hard global scheduler.
        (0.0, 1.0),
        rows[:12],
        rows[12:18],
        intervention_arity=1,
        composition_constants=(0.0, 1.0),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=4_000,
        max_composition_candidates_total=budget,
        ablation_max_candidates=2_000,
        composition_beam_width=96,
    )


def _semantic_selection(receipt) -> tuple[str, ...] | None:
    if not receipt.passed or receipt.selected is None:
        return None
    return tuple(sorted(receipt.selected.semantic_profile_ids))


def test_triplet_global_budget_outcome_is_semantically_invariant_to_field_layout() -> None:
    """Hard global cap must not turn equivalent layouts into solve vs abstain.

    The contract deliberately does not demand success under a tight budget.  It
    only demands the same semantic outcome.  A fair scheduler may solve both or
    fail closed on both; positional/hash ordering alone may not decide authority.
    """
    orders = (
        ('a', 'b', 'c'),
        ('c', 'a', 'b'),
        ('b', 'c', 'a'),
    )

    # Roomy control: all layouts must expose the same semantic causal triplet.
    roomy = tuple(_run(order, 80_000) for order in orders)
    assert all(receipt.passed for receipt in roomy)
    selections = tuple(_semantic_selection(receipt) for receipt in roomy)
    assert selections[0] is not None
    assert selections[1:] == selections[:1] * 2

    # Sweep several genuinely hard global caps.  Exact pass/abstain vectors and
    # selected semantic triplets, when any, must agree across layouts.
    for budget in (400, 800, 1_600, 3_200, 6_400, 12_800):
        receipts = tuple(_run(order, budget) for order in orders)
        passed = tuple(receipt.passed for receipt in receipts)
        assert passed == (passed[0],) * len(passed), (budget, passed, tuple(r.reason for r in receipts))
        selected = tuple(_semantic_selection(receipt) for receipt in receipts)
        assert selected == (selected[0],) * len(selected), (budget, selected)
        assert all(receipt.false_accepts == 0 for receipt in receipts)
