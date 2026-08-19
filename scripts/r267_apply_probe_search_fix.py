from __future__ import annotations

from pathlib import Path


path = Path('cogcoder/r267_three_probe_causal_composition.py')
text = path.read_text()
marker = "\ndef _synthesize_r267_expression(\n"
if marker not in text:
    raise SystemExit('R2.67 synthesis insertion point changed concurrently')
if 'def _synthesize_required_three_probe_skeleton(' not in text:
    raise SystemExit('required-probe search patch must be applied first')

helper = r'''
def _synthesize_bilinear_pair_skeleton(
    field_names: Sequence[str],
    examples: Sequence[OperatorExample],
    *,
    max_candidates: int,
) -> _ExpressionSearchReceipt:
    """Enumerate the finite depth-2 pair-product closure over available fields.

    The closure is field-agnostic: it does not choose which inputs participate in
    the target.  It enumerates every unordered field product and every ordered pair
    of those products under the trusted outer arithmetic operators.  This makes the
    tri-bilinear probe subproblem complete for its declared depth without widening
    the R2.56 operator semantics.
    """
    fields = tuple(sorted({str(value).strip() for value in field_names if str(value).strip()}))
    rows = tuple(examples)
    limit = int(max_candidates)
    if limit < 1:
        raise ValueError('max_candidates must be positive')
    if len(fields) < 2:
        return _ExpressionSearchReceipt(False, None, 0, 0, 0, 'bilinear_pair_no_fields')
    target = tuple(_finite_json_value(row.expected) for row in rows)
    considered = 0
    evaluations = 0
    digests: set[str] = set()
    semantic_seen: set[str] = set()
    product_terms = tuple(
        Binary('mul', Field(left), Field(right))
        for left, right in itertools.combinations(fields, 2)
    )
    outer_ops = ('add', 'sub', 'min', 'max')

    for left in product_terms:
        for right in product_terms:
            for op in outer_ops:
                if considered >= limit:
                    return _ExpressionSearchReceipt(
                        False, None, considered, evaluations, len(semantic_seen),
                        'bilinear_pair_budget_exhausted',
                    )
                expr = Binary(op, left, right)
                digest = expr_digest(expr)
                if digest in digests:
                    continue
                digests.add(digest)
                considered += 1
                values, count = _evaluate_vector(expr, rows)
                evaluations += count
                if values is None:
                    continue
                semantic_seen.add(semantic_vector_key(values))
                if all(_equivalent(actual, expected) for actual, expected in zip(values, target, strict=True)):
                    return _ExpressionSearchReceipt(
                        True, expr, considered, evaluations, len(semantic_seen),
                        'bilinear_pair_exact',
                    )
    return _ExpressionSearchReceipt(
        False, None, considered, evaluations, len(semantic_seen),
        'bilinear_pair_no_exact_expression',
    )

'''
text = text.replace(marker, '\n' + helper + 'def _synthesize_r267_expression(\n', 1)

old = """    remaining_after_structural = max_candidates - structural_considered\n    if remaining_after_structural < 1:\n        return _ExpressionSearchReceipt(\n            False, None, structural_considered, structural_evaluations,\n            structural_semantics, 'r267_expression_budget_exhausted',\n        )\n    router_budget = min(8_000, max(1, remaining_after_structural // 4))\n"""
new = """    remaining_after_structural = max_candidates - structural_considered\n    if remaining_after_structural < 1:\n        return _ExpressionSearchReceipt(\n            False, None, structural_considered, structural_evaluations,\n            structural_semantics, 'r267_expression_budget_exhausted',\n        )\n\n    bilinear_considered = 0\n    bilinear_evaluations = 0\n    bilinear_semantics = 0\n    if int(max_depth) >= 2:\n        bilinear_budget = min(remaining_after_structural, max(128, min(5_000, remaining_after_structural // 4)))\n        bilinear = _synthesize_bilinear_pair_skeleton(\n            tuple(field_names), tuple(examples), max_candidates=bilinear_budget,\n        )\n        bilinear_considered = bilinear.candidates_considered\n        bilinear_evaluations = bilinear.evaluations\n        bilinear_semantics = bilinear.semantic_candidates\n        if bilinear.passed and bilinear.expression is not None:\n            return _ExpressionSearchReceipt(\n                True, bilinear.expression,\n                structural_considered + bilinear_considered,\n                structural_evaluations + bilinear_evaluations,\n                structural_semantics + bilinear_semantics,\n                bilinear.reason,\n            )\n\n    remaining_after_bilinear = remaining_after_structural - bilinear_considered\n    if remaining_after_bilinear < 1:\n        return _ExpressionSearchReceipt(\n            False, None, structural_considered + bilinear_considered,\n            structural_evaluations + bilinear_evaluations,\n            structural_semantics + bilinear_semantics,\n            'r267_expression_budget_exhausted',\n        )\n    router_budget = min(8_000, max(1, remaining_after_bilinear // 4))\n"""
if old not in text:
    raise SystemExit('R2.67 post-structural budget surface changed concurrently')
text = text.replace(old, new, 1)

text = text.replace(
    'structural_considered + router.candidates_considered,\n            structural_evaluations + router.search_evaluations,\n            structural_semantics + router.semantic_candidates,',
    'structural_considered + bilinear_considered + router.candidates_considered,\n            structural_evaluations + bilinear_evaluations + router.search_evaluations,\n            structural_semantics + bilinear_semantics + router.semantic_candidates,',
    1,
)
text = text.replace(
    'remaining = remaining_after_structural - router.candidates_considered',
    'remaining = remaining_after_bilinear - router.candidates_considered',
    1,
)
text = text.replace(
    'structural_considered + router.candidates_considered,\n            structural_evaluations + router.search_evaluations,\n            structural_semantics + router.semantic_candidates,',
    'structural_considered + bilinear_considered + router.candidates_considered,\n            structural_evaluations + bilinear_evaluations + router.search_evaluations,\n            structural_semantics + bilinear_semantics + router.semantic_candidates,',
    1,
)
text = text.replace(
    'structural_considered + router.candidates_considered + arithmetic.candidates_considered,\n        structural_evaluations + router.search_evaluations + arithmetic.evaluations,\n        structural_semantics + router.semantic_candidates + arithmetic.semantic_candidates,',
    'structural_considered + bilinear_considered + router.candidates_considered + arithmetic.candidates_considered,\n        structural_evaluations + bilinear_evaluations + router.search_evaluations + arithmetic.evaluations,\n        structural_semantics + bilinear_semantics + router.semantic_candidates + arithmetic.semantic_candidates,',
    1,
)

path.write_text(text)
print('R267_BILINEAR_PROBE_SEARCH_PATCH_APPLIED')
