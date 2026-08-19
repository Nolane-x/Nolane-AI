from __future__ import annotations

from collections.abc import Mapping

import cogcoder.r267_three_probe_causal_composition as r267
from cogcoder.r256_operator_dsl import Binary, Field


FIELDS = ('a', 'b', 'c')
ROWS = tuple((float(i), float(100 + i), float(10_000 + i)) for i in range(1, 19))


def _contexts() -> tuple[dict[str, float], ...]:
    return tuple(dict(zip(FIELDS, row, strict=True)) for row in ROWS)


def _oracle(row: Mapping[str, object]) -> float:
    a = float(row['a'])
    b = float(row['b'])
    c = float(row['c'])
    return a * b + b * c + c * a


def test_uncertified_lower_order_search_miss_cannot_authorize_three_probe_necessity(monkeypatch) -> None:
    """A bounded search miss is not a proof that a lower-order program cannot exist.

    The public lower-order evidence in this corpus is injective, so there is no
    collision certificate.  A synthetic search oracle supplies an exact full
    three-probe expression but reports a non-budget no-expression result for
    every proper subset.  Strong causal authority must abstain rather than
    reinterpret the bounded miss as a necessity proof.
    """
    rows = _contexts()

    def bounded_search(field_names, constants, examples, *, max_depth, max_candidates, beam_width):
        names = set(map(str, field_names))
        if {'__p0', '__p1', '__p2'} <= names:
            expression = Binary('add', Binary('add', Field('__p0'), Field('__p1')), Field('__p2'))
            return r267._ExpressionSearchReceipt(
                True,
                expression,
                1,
                len(examples),
                1,
                'synthetic_full_exact',
            )
        return r267._ExpressionSearchReceipt(
            False,
            None,
            1,
            len(examples),
            1,
            'r267_complete_grammar_no_expression',
        )

    monkeypatch.setattr(r267, '_synthesize_r267_expression', bounded_search)
    receipt = r267.discover_three_probe_structure(
        _oracle,
        FIELDS,
        (0.0,),
        rows[:12],
        rows[12:18],
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=100,
        max_composition_candidates_total=100,
        ablation_max_candidates=100,
        composition_beam_width=8,
    )

    assert receipt.passed is False
    assert receipt.selected is None
    assert receipt.false_accepts == 0
    assert receipt.reason == 'ablation_search_inconclusive'
