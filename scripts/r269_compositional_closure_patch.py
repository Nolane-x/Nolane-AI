from __future__ import annotations

from pathlib import Path

PATH = Path("cogcoder/r269_transfer_runtime.py")
text = PATH.read_text(encoding="utf-8")
start = text.index("def _scratch_hypotheses(")
end = text.index("\n\ndef _predict(", start)
new = '''def _scratch_hypotheses(signature: PublicTaskSignature, config: MetaLearningConfig) -> list[_Hypothesis]:
    rows: list[_Hypothesis] = []
    seen: set[str] = set()
    key_cache: dict[str, str] = {}

    def key_for(expr: Expr) -> str:
        syntax = expr_digest(expr)
        key = key_cache.get(syntax)
        if key is None:
            key = _structural_key(expr, signature)
            key_cache[syntax] = key
        return key

    def add(expr: Expr, *, key: str | None = None) -> bool:
        semantic_key = key if key is not None else key_for(expr)
        if semantic_key in seen:
            return True
        seen.add(semantic_key)
        rows.append(_Hypothesis(expr, 'scratch.' + expr_digest(expr), 'scratch', len(rows)))
        return len(rows) < config.scratch_candidate_cap

    def role_coverage(expr: Expr) -> frozenset[str]:
        if isinstance(expr, Field):
            return frozenset((expr.name,))
        if isinstance(expr, Const):
            return frozenset()
        if isinstance(expr, Unary):
            return role_coverage(expr.arg)
        if isinstance(expr, Binary):
            return role_coverage(expr.left) | role_coverage(expr.right)
        if isinstance(expr, IfElse):
            return role_coverage(expr.condition) | role_coverage(expr.when_true) | role_coverage(expr.when_false)
        raise TypeError(f'unsupported expression type: {type(expr).__name__}')

    def add_ranked_layer(buckets: Mapping[str, Sequence[Expr]]) -> bool:
        ranked: dict[str, list[Expr]] = {}
        for op in signature.allowed_binary_ops:
            # Cheap syntactic dedupe first.  Complete-domain semantic proofs are
            # intentionally evaluated lazily only for candidates that the public
            # target-independent scheduler actually reaches before the cap.
            syntax_distinct: dict[str, Expr] = {}
            for expr in buckets.get(op, ()):
                syntax_distinct.setdefault(expr_digest(expr), expr)
            ranked[op] = sorted(
                syntax_distinct.values(),
                key=lambda expr: (
                    -len(role_coverage(expr)),
                    expr.cost,
                    expr_digest(expr),
                ),
            )
        indexes = {op: 0 for op in signature.allowed_binary_ops}
        while True:
            progressed = False
            for op in signature.allowed_binary_ops:
                index = indexes[op]
                bucket = ranked[op]
                if index >= len(bucket):
                    continue
                progressed = True
                indexes[op] = index + 1
                if not add(bucket[index]):
                    return False
            if not progressed:
                return True

    fields = tuple(Field(name) for name in signature.role_names)
    for field in fields:
        if not add(field):
            return rows
    if config.scratch_max_depth == 0:
        return rows

    # Level 1 is small enough to materialize proof-distinct.  Raw aliases are
    # collapsed before they can multiply into deeper construction layers.
    level1_by_key: dict[str, Expr] = {}
    for op in signature.allowed_binary_ops:
        for left in fields:
            for right in fields:
                expr = Binary(op, left, right)
                key = key_for(expr)
                level1_by_key.setdefault(key, expr)
                if not add(expr, key=key):
                    return rows
    if config.scratch_max_depth == 1:
        return rows
    level1 = tuple(level1_by_key.values())

    # Complete binary depth-2 grammar: nested+field, field+nested and the
    # previously omitted balanced nested+nested family.  Scheduling uses only
    # public structure (role coverage, cost, operator round-robin), never target
    # outputs or hidden labels.  Semantic proof dedupe is lazy under the cap.
    depth2_buckets: dict[str, list[Expr]] = {
        op: [] for op in signature.allowed_binary_ops
    }
    for op in signature.allowed_binary_ops:
        bucket = depth2_buckets[op]
        for nested in level1:
            for field in fields:
                bucket.append(Binary(op, nested, field))
                bucket.append(Binary(op, field, nested))
        for left in level1:
            for right in level1:
                bucket.append(Binary(op, left, right))
    if not add_ranked_layer(depth2_buckets):
        return rows
    if config.scratch_max_depth == 2:
        return rows

    # Depth 3 expands only after the lower layer.  It uses the same lazy,
    # target-independent policy, so larger budgets buy semantic breadth rather
    # than paying the full Cartesian proof cost up front.
    previous = tuple(row.expression for row in rows)
    frontier = tuple(expr for expr in previous if expr.depth == 2)
    lower = tuple(expr for expr in previous if expr.depth <= 2)
    depth3_buckets: dict[str, list[Expr]] = {
        op: [] for op in signature.allowed_binary_ops
    }
    for op in signature.allowed_binary_ops:
        bucket = depth3_buckets[op]
        for left in frontier:
            for right in lower:
                bucket.append(Binary(op, left, right))
                bucket.append(Binary(op, right, left))
    add_ranked_layer(depth3_buckets)
    return rows
'''
compile(new, str(PATH), "exec")
updated = text[:start] + new + text[end:]
compile(updated, str(PATH), "exec")
PATH.write_text(updated, encoding="utf-8")
