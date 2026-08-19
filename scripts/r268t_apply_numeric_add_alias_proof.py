from __future__ import annotations

from pathlib import Path


SOURCE = Path('cogcoder/r268_cross_task_causal_transfer.py')

OLD = '''_PROVEN_COMMUTATIVE_NUMERIC_OPS = frozenset(('add', 'mul'))


def _proven_structural_alias_key(expr: Expr) -> str:
    if isinstance(expr, Field):
        return json.dumps(('field', expr.name), separators=(',', ':'), ensure_ascii=True)
    if isinstance(expr, Const):
        return json.dumps(('const', expr.value), separators=(',', ':'), ensure_ascii=True)
    if isinstance(expr, Unary):
        return json.dumps(
            ('unary', expr.op, _proven_structural_alias_key(expr.arg)),
            separators=(',', ':'),
            ensure_ascii=True,
        )
    if isinstance(expr, Binary):
        left = _proven_structural_alias_key(expr.left)
        right = _proven_structural_alias_key(expr.right)
        if expr.op in _PROVEN_COMMUTATIVE_NUMERIC_OPS and right < left:
            left, right = right, left
        return json.dumps(
            ('binary', expr.op, left, right),
            separators=(',', ':'),
            ensure_ascii=True,
        )
    if isinstance(expr, IfElse):
        return json.dumps(
            (
                'ifelse',
                _proven_structural_alias_key(expr.condition),
                _proven_structural_alias_key(expr.when_true),
                _proven_structural_alias_key(expr.when_false),
            ),
            separators=(',', ':'),
            ensure_ascii=True,
        )
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')
'''

NEW = '''def _proven_numeric_expr(expr: Expr) -> bool:
    # Probe-role contexts are validated as finite numeric values before oracle
    # authority is exercised. This helper proves only the *result type* needed
    # to justify commutative numeric addition; it does not prove totality.
    if isinstance(expr, Field):
        return True
    if isinstance(expr, Const):
        return isinstance(expr.value, (int, float)) and not isinstance(expr.value, bool)
    if isinstance(expr, Unary):
        if expr.op in ('abs', 'neg'):
            return _proven_numeric_expr(expr.arg)
        if expr.op == 'len':
            return True
        return False
    if isinstance(expr, Binary):
        if expr.op in ('add', 'sub', 'mul', 'div', 'min', 'max'):
            return _proven_numeric_expr(expr.left) and _proven_numeric_expr(expr.right)
        return False
    if isinstance(expr, IfElse):
        return (
            _proven_numeric_expr(expr.when_true)
            and _proven_numeric_expr(expr.when_false)
        )
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')


def _proven_structural_alias_key(expr: Expr) -> str:
    if isinstance(expr, Field):
        return json.dumps(('field', expr.name), separators=(',', ':'), ensure_ascii=True)
    if isinstance(expr, Const):
        return json.dumps(('const', expr.value), separators=(',', ':'), ensure_ascii=True)
    if isinstance(expr, Unary):
        return json.dumps(
            ('unary', expr.op, _proven_structural_alias_key(expr.arg)),
            separators=(',', ':'),
            ensure_ascii=True,
        )
    if isinstance(expr, Binary):
        left = _proven_structural_alias_key(expr.left)
        right = _proven_structural_alias_key(expr.right)
        commutative_proven = (
            expr.op == 'mul'
            or (
                expr.op == 'add'
                and _proven_numeric_expr(expr.left)
                and _proven_numeric_expr(expr.right)
            )
        )
        if commutative_proven and right < left:
            left, right = right, left
        return json.dumps(
            ('binary', expr.op, left, right),
            separators=(',', ':'),
            ensure_ascii=True,
        )
    if isinstance(expr, IfElse):
        return json.dumps(
            (
                'ifelse',
                _proven_structural_alias_key(expr.condition),
                _proven_structural_alias_key(expr.when_true),
                _proven_structural_alias_key(expr.when_false),
            ),
            separators=(',', ':'),
            ensure_ascii=True,
        )
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')
'''


def main() -> None:
    text = SOURCE.read_text(encoding='utf-8')
    if 'def _proven_numeric_expr(' in text:
        print('R268T_NUMERIC_ADD_ALIAS_PROOF_ALREADY_MATERIALIZED')
        return
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f'expected exactly one alias-proof boundary, found {count}')
    text = text.replace(OLD, NEW, 1)
    compile(text, str(SOURCE), 'exec')
    SOURCE.write_text(text, encoding='utf-8')
    print('R268T_NUMERIC_ADD_ALIAS_PROOF_MATERIALIZED')


if __name__ == '__main__':
    main()
