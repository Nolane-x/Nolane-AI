from __future__ import annotations

from pathlib import Path

PATH = Path("cogcoder/r269_transfer_runtime.py")

OLD = '''def _scratch_hypotheses(sig: PublicTaskSignature, cfg: MetaLearningConfig) -> list[_Hypothesis]:
    rows: list[_Hypothesis] = []
    seen: set[str] = set()

    def add(expr: Expr) -> bool:
        key = _structural_key(expr)
        if key in seen:
            return True
        seen.add(key)
        rows.append(_Hypothesis(expr, 'scratch.' + expr_digest(expr), 'scratch', len(rows)))
        return len(rows) < cfg.scratch_candidate_cap

    fields = tuple(Field(name) for name in sig.role_names)
    for field in fields:
        if not add(field):
            return rows
    if cfg.scratch_max_depth == 0:
        return rows

    level1: list[Expr] = []
    for op in sig.allowed_binary_ops:
        for left in fields:
            for right in fields:
                expr = Binary(op, left, right)
                level1.append(expr)
                if not add(expr):
                    return rows
    if cfg.scratch_max_depth == 1:
        return rows

    for op in sig.allowed_binary_ops:
        for nested in level1:
            for field in fields:
                if not add(Binary(op, nested, field)):
                    return rows
                if not add(Binary(op, field, nested)):
                    return rows
    return rows
'''

NEW = '''def _scratch_hypotheses(sig: PublicTaskSignature, cfg: MetaLearningConfig) -> list[_Hypothesis]:
    rows: list[_Hypothesis] = []
    seen: set[str] = set()

    def add(expr: Expr) -> bool:
        key = _structural_key(expr)
        if key in seen:
            return True
        seen.add(key)
        rows.append(_Hypothesis(expr, 'scratch.' + expr_digest(expr), 'scratch', len(rows)))
        return len(rows) < cfg.scratch_candidate_cap

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
        raise TypeError(type(expr).__name__)

    fields = tuple(Field(name) for name in sig.role_names)
    for field in fields:
        if not add(field):
            return rows
    if cfg.scratch_max_depth == 0:
        return rows

    # Materialize level-1 proof-distinct expressions once.  The old enumerator
    # retained raw commutative aliases here, allowing representation duplicates
    # to dominate the depth-2 construction order.
    level1_by_key: dict[str, Expr] = {}
    for op in sig.allowed_binary_ops:
        for left in fields:
            for right in fields:
                expr = Binary(op, left, right)
                key = _structural_key(expr)
                level1_by_key.setdefault(key, expr)
                if not add(expr):
                    return rows
    if cfg.scratch_max_depth == 1:
        return rows
    level1 = tuple(level1_by_key[key] for key in sorted(level1_by_key))

    # Depth-2 closure includes both nested+field and nested+nested shapes.
    # Build a target-output-independent pool, then schedule by public role
    # coverage and round-robin root operator.  This prevents one syntactic
    # shape/operator from starving another under a proof-distinct cap.
    by_op: dict[str, dict[str, Expr]] = {op: {} for op in sig.allowed_binary_ops}
    for op in sig.allowed_binary_ops:
        bucket = by_op[op]
        for nested in level1:
            for field in fields:
                for expr in (Binary(op, nested, field), Binary(op, field, nested)):
                    key = _structural_key(expr)
                    if key not in seen:
                        bucket.setdefault(key, expr)
        for left in level1:
            for right in level1:
                expr = Binary(op, left, right)
                key = _structural_key(expr)
                if key not in seen:
                    bucket.setdefault(key, expr)

    ranked: dict[str, list[Expr]] = {}
    for op in sig.allowed_binary_ops:
        ranked[op] = sorted(
            by_op[op].values(),
            key=lambda expr: (-len(role_coverage(expr)), expr.cost, _structural_key(expr)),
        )

    indexes = {op: 0 for op in sig.allowed_binary_ops}
    while True:
        progressed = False
        for op in sig.allowed_binary_ops:
            index = indexes[op]
            bucket = ranked[op]
            if index >= len(bucket):
                continue
            progressed = True
            indexes[op] = index + 1
            if not add(bucket[index]):
                return rows
        if not progressed:
            break
    return rows
'''

text = PATH.read_text(encoding="utf-8")
if text.count(OLD) != 1:
    raise SystemExit(f"expected exactly one scratch function boundary, found {text.count(OLD)}")
updated = text.replace(OLD, NEW)
compile(updated, str(PATH), "exec")
PATH.write_text(updated, encoding="utf-8")
