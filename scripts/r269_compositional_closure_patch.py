from __future__ import annotations

from pathlib import Path

PATH = Path("cogcoder/r269_transfer_runtime.py")
text = PATH.read_text(encoding="utf-8")
start = text.index("def _scratch_hypotheses(")
end = text.index("\n\ndef _predict(", start)
old = text[start:end]
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

    def add_ranked_layer(buckets: Mapping[str, Mapping[str, Expr]]) -> bool:
        ranked: dict[str, list[tuple[str, Expr]]] = {}
        for op in signature.allowed_binary_ops:
            ranked[op] = sorted(
                buckets.get(op, {}).items(),
                key=lambda item: (
                    -len(role_coverage(item[1])),
                    item[1].cost,
                    expr_digest(item[1]),
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
                semantic_key, expr = bucket[index]
                if not add(expr, key=semantic_key):
                    return False
            if not progressed:
                return True

    fields = tuple(Field(name) for name in signature.role_names)
    for field in fields:
        if not add(field):
            return rows
    if config.scratch_max_depth == 0:
        return rows

    # Level 1 is materialized proof-distinct.  Raw commutative/extensional
    # aliases must not get multiplied again when constructing deeper layers.
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

    # A complete binary depth-2 layer contains both nested+field and
    # nested+nested shapes.  The previous enumerator omitted the balanced
    # nested+nested family entirely.  Candidate scheduling is target-output
    # independent: prefer public role coverage, then lower syntactic cost, and
    # round-robin root operators so one operator cannot consume the whole cap.
    depth2_buckets: dict[str, dict[str, Expr]] = {
        op: {} for op in signature.allowed_binary_ops
    }
    for op in signature.allowed_binary_ops:
        bucket = depth2_buckets[op]
        for nested in level1:
            for field in fields:
                for expr in (Binary(op, nested, field), Binary(op, field, nested)):
                    key = key_for(expr)
                    if key not in seen:
                        bucket.setdefault(key, expr)
        for left in level1:
            for right in level1:
                expr = Binary(op, left, right)
                key = key_for(expr)
                if key not in seen:
                    bucket.setdefault(key, expr)
    if not add_ranked_layer(depth2_buckets):
        return rows
    if config.scratch_max_depth == 2:
        return rows

    # Depth 3 expands only after the semantically complete lower layer.  Keep
    # the same target-independent scheduling rule so larger caps buy breadth
    # before representation duplicates or a single root operator.
    previous = tuple(row.expression for row in rows)
    frontier = tuple(expr for expr in previous if expr.depth == 2)
    lower = tuple(expr for expr in previous if expr.depth <= 2)
    depth3_buckets: dict[str, dict[str, Expr]] = {
        op: {} for op in signature.allowed_binary_ops
    }
    for op in signature.allowed_binary_ops:
        bucket = depth3_buckets[op]
        for left in frontier:
            for right in lower:
                for expr in (Binary(op, left, right), Binary(op, right, left)):
                    key = key_for(expr)
                    if key not in seen:
                        bucket.setdefault(key, expr)
    add_ranked_layer(depth3_buckets)
    return rows
'''
compile(new, str(PATH), "exec")
updated = text[:start] + new + text[end:]
compile(updated, str(PATH), "exec")
PATH.write_text(updated, encoding="utf-8")
