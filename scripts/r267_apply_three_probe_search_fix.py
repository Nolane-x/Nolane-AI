from __future__ import annotations

from pathlib import Path


path = Path('cogcoder/r267_three_probe_causal_composition.py')
text = path.read_text()

marker = "\ndef _synthesize_r267_expression(\n"
if marker not in text:
    raise SystemExit('R2.67 synthesis insertion point changed concurrently')

helper = r'''
def _synthesize_required_three_probe_skeleton(
    constants: Sequence[object],
    examples: Sequence[OperatorExample],
    *,
    max_candidates: int,
) -> _ExpressionSearchReceipt:
    """Search a bounded neutral algebraic closure that structurally requires all three probes.

    This is not a host-supplied target formula: every binary operator, association,
    probe permutation and authorized constant transform is enumerated and judged only
    by public example behavior.  It exists because the inherited R2.66 router search
    deliberately prioritizes one-step leaves and IfElse structure rather than nested
    three-input arithmetic trees.
    """
    rows = tuple(examples)
    target = tuple(_finite_json_value(row.expected) for row in rows)
    limit = int(max_candidates)
    if limit < 1:
        raise ValueError('max_candidates must be positive')
    considered = 0
    evaluations = 0
    digests: set[str] = set()
    semantic_seen: set[str] = set()
    numeric_ops = ('add', 'sub', 'mul', 'div', 'min', 'max')
    outer_constant_ops = ('add', 'sub', 'mul', 'div')
    probe_fields = (Field('__p0'), Field('__p1'), Field('__p2'))
    authorized_constants: list[Const] = []
    constant_keys: set[str] = set()
    for raw in constants:
        try:
            value = _finite_json_value(raw)
            constant = Const(value)
            key = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
        except (TypeError, ValueError):
            continue
        if key not in constant_keys:
            constant_keys.add(key)
            authorized_constants.append(constant)

    def consider(expr: Expr) -> _ExpressionSearchReceipt | None:
        nonlocal considered, evaluations
        if considered >= limit:
            return _ExpressionSearchReceipt(
                False, None, considered, evaluations, len(semantic_seen),
                'required_three_probe_budget_exhausted',
            )
        digest = expr_digest(expr)
        if digest in digests:
            return None
        digests.add(digest)
        considered += 1
        values, count = _evaluate_vector(expr, rows)
        evaluations += count
        if values is None:
            return None
        semantic_seen.add(semantic_vector_key(values))
        if all(_equivalent(actual, expected) for actual, expected in zip(values, target, strict=True)):
            return _ExpressionSearchReceipt(
                True, expr, considered, evaluations, len(semantic_seen),
                'required_three_probe_exact',
            )
        return None

    for first, second, third in itertools.permutations(probe_fields):
        for inner_op in numeric_ops:
            try:
                inner_left = Binary(inner_op, first, second)
                inner_right = Binary(inner_op, second, third)
            except (TypeError, ValueError):
                continue
            for outer_op in numeric_ops:
                bases: list[Expr] = []
                try:
                    bases.append(Binary(outer_op, inner_left, third))
                except (TypeError, ValueError):
                    pass
                try:
                    bases.append(Binary(outer_op, first, inner_right))
                except (TypeError, ValueError):
                    pass
                for base in bases:
                    hit = consider(base)
                    if hit is not None:
                        return hit
                    for constant in authorized_constants:
                        for op in outer_constant_ops:
                            for transformed in (
                                Binary(op, base, constant),
                                Binary(op, constant, base),
                            ):
                                hit = consider(transformed)
                                if hit is not None:
                                    return hit
    return _ExpressionSearchReceipt(
        False, None, considered, evaluations, len(semantic_seen),
        'required_three_probe_no_exact_expression',
    )

'''
text = text.replace(marker, '\n' + helper + 'def _synthesize_r267_expression(\n', 1)

old = """    max_candidates = int(max_candidates)\n    if max_candidates < 1:\n        raise ValueError('max_candidates must be positive')\n    router_budget = min(8_000, max(1, max_candidates // 4))\n    router = synthesize_contextual_expression(\n"""
new = """    max_candidates = int(max_candidates)\n    if max_candidates < 1:\n        raise ValueError('max_candidates must be positive')\n\n    structural_considered = 0\n    structural_evaluations = 0\n    structural_semantics = 0\n    required_probes = {'__p0', '__p1', '__p2'}\n    if required_probes <= set(map(str, field_names)):\n        structural_budget = min(max_candidates, max(64, min(10_000, max_candidates // 3)))\n        structural = _synthesize_required_three_probe_skeleton(\n            tuple(constants), tuple(examples), max_candidates=structural_budget,\n        )\n        structural_considered = structural.candidates_considered\n        structural_evaluations = structural.evaluations\n        structural_semantics = structural.semantic_candidates\n        if structural.passed and structural.expression is not None:\n            return structural\n\n    remaining_after_structural = max_candidates - structural_considered\n    if remaining_after_structural < 1:\n        return _ExpressionSearchReceipt(\n            False, None, structural_considered, structural_evaluations,\n            structural_semantics, 'r267_expression_budget_exhausted',\n        )\n    router_budget = min(8_000, max(1, remaining_after_structural // 4))\n    router = synthesize_contextual_expression(\n"""
if old not in text:
    raise SystemExit('R2.67 synthesis budget surface changed concurrently')
text = text.replace(old, new, 1)

old2 = """        return _ExpressionSearchReceipt(\n            True,\n            router.expression,\n            router.candidates_considered,\n            router.search_evaluations,\n            router.semantic_candidates,\n            'r266_contextual_exact',\n        )\n    remaining = max_candidates - router.candidates_considered\n"""
new2 = """        return _ExpressionSearchReceipt(\n            True,\n            router.expression,\n            structural_considered + router.candidates_considered,\n            structural_evaluations + router.search_evaluations,\n            structural_semantics + router.semantic_candidates,\n            'r266_contextual_exact',\n        )\n    remaining = remaining_after_structural - router.candidates_considered\n"""
if old2 not in text:
    raise SystemExit('R2.67 router accounting surface changed concurrently')
text = text.replace(old2, new2, 1)

old3 = """        return _ExpressionSearchReceipt(\n            False,\n            None,\n            router.candidates_considered,\n            router.search_evaluations,\n            router.semantic_candidates,\n            'r267_expression_budget_exhausted',\n        )\n"""
new3 = """        return _ExpressionSearchReceipt(\n            False,\n            None,\n            structural_considered + router.candidates_considered,\n            structural_evaluations + router.search_evaluations,\n            structural_semantics + router.semantic_candidates,\n            'r267_expression_budget_exhausted',\n        )\n"""
if old3 not in text:
    raise SystemExit('R2.67 exhausted accounting surface changed concurrently')
text = text.replace(old3, new3, 1)

old4 = """    return _ExpressionSearchReceipt(\n        arithmetic.passed,\n        arithmetic.expression,\n        router.candidates_considered + arithmetic.candidates_considered,\n        router.search_evaluations + arithmetic.evaluations,\n        router.semantic_candidates + arithmetic.semantic_candidates,\n        arithmetic.reason,\n    )\n"""
new4 = """    return _ExpressionSearchReceipt(\n        arithmetic.passed,\n        arithmetic.expression,\n        structural_considered + router.candidates_considered + arithmetic.candidates_considered,\n        structural_evaluations + router.search_evaluations + arithmetic.evaluations,\n        structural_semantics + router.semantic_candidates + arithmetic.semantic_candidates,\n        arithmetic.reason,\n    )\n"""
if old4 not in text:
    raise SystemExit('R2.67 final accounting surface changed concurrently')
text = text.replace(old4, new4, 1)

path.write_text(text)
print('R267_REQUIRED_THREE_PROBE_SEARCH_PATCH_APPLIED')
