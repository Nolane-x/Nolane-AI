from __future__ import annotations

from collections.abc import Mapping

import cogcoder.r267_three_probe_causal_composition as r267
from cogcoder.r256_operator_dsl import Binary, Field

FIELDS = ('a', 'b', 'c')
ROWS = tuple((float(i), float(100 + i), float(10000 + i)) for i in range(1, 19))


def _contexts() -> tuple[dict[str, float], ...]:
    return tuple(dict(zip(FIELDS, row, strict=True)) for row in ROWS)


def _oracle(row: Mapping[str, object]) -> float:
    a, b, c = float(row['a']), float(row['b']), float(row['c'])
    return a * b + b * c + c * a


def test_no_collision_lower_order_search_miss_is_inconclusive(monkeypatch) -> None:
    """A bounded/beam search miss is not an impossibility certificate.

    This corpus deliberately has unique public evidence for every lower-order
    subset, so there is no information-theoretic collision witness.  We stub
    the bounded expression search to succeed for the full triplet and return a
    non-budget 'no expression' result for lower-order subsets.  Authority must
    fail closed rather than interpreting the search miss as causal necessity.
    """
    rows = _contexts()

    def bounded_search(field_names, constants, examples, *, max_depth, max_candidates, beam_width):
        names = set(map(str, field_names))
        if {'__p0', '__p1', '__p2'} <= names:
            expression = Binary('add', Binary('add', Field('__p0'), Field('__p1')), Field('__p2'))
            return r267._ExpressionSearchReceipt(True, expression, 1, len(examples), 1, 'synthetic_full_exact')
        return r267._ExpressionSearchReceipt(False, None, 1, len(examples), 1, 'r267_complete_grammar_no_expression')

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
