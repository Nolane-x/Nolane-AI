from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Iterable, Mapping


_UNARY_OPS = ('abs', 'neg', 'strip', 'lower', 'upper', 'len', 'not')
_BINARY_OPS = (
    'add', 'sub', 'mul', 'div', 'min', 'max',
    'eq', 'ne', 'lt', 'le', 'gt', 'ge', 'and', 'or',
)


def _nonempty(value: str, name: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f'{name} must be non-empty')
    return value


def _json_scalar(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('constants must be finite')
        return value
    raise TypeError('constants must be JSON scalar values')


class Expr:
    @property
    def depth(self) -> int:
        raise NotImplementedError

    @property
    def cost(self) -> int:
        raise NotImplementedError

    def to_data(self) -> dict[str, object]:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class Field(Expr):
    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, 'name', _nonempty(self.name, 'field name'))

    @property
    def depth(self) -> int:
        return 0

    @property
    def cost(self) -> int:
        return 1

    def to_data(self) -> dict[str, object]:
        return {'field': self.name}


@dataclass(frozen=True, slots=True)
class Const(Expr):
    value: object

    def __post_init__(self) -> None:
        object.__setattr__(self, 'value', _json_scalar(self.value))

    @property
    def depth(self) -> int:
        return 0

    @property
    def cost(self) -> int:
        return 1

    def to_data(self) -> dict[str, object]:
        return {'const': self.value}


@dataclass(frozen=True, slots=True)
class Unary(Expr):
    op: str
    arg: Expr

    def __post_init__(self) -> None:
        op = _nonempty(self.op, 'unary op')
        if op not in _UNARY_OPS:
            raise ValueError(f'unsupported unary op: {op}')
        if not isinstance(self.arg, Expr):
            raise TypeError('unary arg must be Expr')
        object.__setattr__(self, 'op', op)

    @property
    def depth(self) -> int:
        return 1 + self.arg.depth

    @property
    def cost(self) -> int:
        return 1 + self.arg.cost

    def to_data(self) -> dict[str, object]:
        return {'op': self.op, 'arg': self.arg.to_data()}


@dataclass(frozen=True, slots=True)
class Binary(Expr):
    op: str
    left: Expr
    right: Expr

    def __post_init__(self) -> None:
        op = _nonempty(self.op, 'binary op')
        if op not in _BINARY_OPS:
            raise ValueError(f'unsupported binary op: {op}')
        if not isinstance(self.left, Expr) or not isinstance(self.right, Expr):
            raise TypeError('binary operands must be Expr')
        object.__setattr__(self, 'op', op)

    @property
    def depth(self) -> int:
        return 1 + max(self.left.depth, self.right.depth)

    @property
    def cost(self) -> int:
        return 1 + self.left.cost + self.right.cost

    def to_data(self) -> dict[str, object]:
        return {'op': self.op, 'left': self.left.to_data(), 'right': self.right.to_data()}


@dataclass(frozen=True, slots=True)
class IfElse(Expr):
    condition: Expr
    when_true: Expr
    when_false: Expr

    def __post_init__(self) -> None:
        if not all(isinstance(row, Expr) for row in (self.condition, self.when_true, self.when_false)):
            raise TypeError('conditional nodes must be Expr')

    @property
    def depth(self) -> int:
        return 1 + max(self.condition.depth, self.when_true.depth, self.when_false.depth)

    @property
    def cost(self) -> int:
        return 1 + self.condition.cost + self.when_true.cost + self.when_false.cost

    def to_data(self) -> dict[str, object]:
        return {
            'op': 'if',
            'condition': self.condition.to_data(),
            'then': self.when_true.to_data(),
            'else': self.when_false.to_data(),
        }


def expr_digest(expr: Expr) -> str:
    if not isinstance(expr, Expr):
        raise TypeError('expr must be Expr')
    payload = json.dumps(expr.to_data(), sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _numeric(value: object) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError('numeric operand required')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('numeric operand must be finite')
    return value


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError('string operand required')
    return value


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise TypeError('boolean operand required')
    return value


def evaluate_expr(expr: Expr, context: Mapping[str, object]) -> object:
    if isinstance(expr, Field):
        if expr.name not in context:
            raise KeyError(expr.name)
        return context[expr.name]
    if isinstance(expr, Const):
        return expr.value
    if isinstance(expr, Unary):
        value = evaluate_expr(expr.arg, context)
        if expr.op == 'abs':
            return abs(_numeric(value))
        if expr.op == 'neg':
            return -_numeric(value)
        if expr.op == 'strip':
            return _string(value).strip()
        if expr.op == 'lower':
            return _string(value).lower()
        if expr.op == 'upper':
            return _string(value).upper()
        if expr.op == 'len':
            if not isinstance(value, (str, tuple, list, dict)):
                raise TypeError('length operand must be string or JSON container')
            return len(value)
        if expr.op == 'not':
            return not _boolean(value)
        raise AssertionError(expr.op)
    if isinstance(expr, Binary):
        left = evaluate_expr(expr.left, context)
        right = evaluate_expr(expr.right, context)
        if expr.op == 'add':
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            return _numeric(left) + _numeric(right)
        if expr.op == 'sub':
            return _numeric(left) - _numeric(right)
        if expr.op == 'mul':
            return _numeric(left) * _numeric(right)
        if expr.op == 'div':
            numerator = _numeric(left)
            denominator = _numeric(right)
            if denominator == 0:
                raise ValueError('division by zero')
            return numerator / denominator
        if expr.op == 'min':
            return min(_numeric(left), _numeric(right))
        if expr.op == 'max':
            return max(_numeric(left), _numeric(right))
        if expr.op == 'eq':
            return left == right
        if expr.op == 'ne':
            return left != right
        if expr.op in {'lt', 'le', 'gt', 'ge'}:
            if isinstance(left, str) and isinstance(right, str):
                pass
            else:
                left = _numeric(left)
                right = _numeric(right)
            return {
                'lt': left < right,
                'le': left <= right,
                'gt': left > right,
                'ge': left >= right,
            }[expr.op]
        if expr.op == 'and':
            return _boolean(left) and _boolean(right)
        if expr.op == 'or':
            return _boolean(left) or _boolean(right)
        raise AssertionError(expr.op)
    if isinstance(expr, IfElse):
        condition = _boolean(evaluate_expr(expr.condition, context))
        return evaluate_expr(expr.when_true if condition else expr.when_false, context)
    raise TypeError('unknown expression node')


def enumerate_expressions(
    field_names: Iterable[str],
    *,
    constants: Iterable[object] = (0, 1, -1, True, False, ''),
    max_depth: int = 2,
    max_candidates: int = 5000,
) -> tuple[Expr, ...]:
    if int(max_depth) < 0:
        raise ValueError('max_depth must be non-negative')
    if int(max_candidates) < 1:
        raise ValueError('max_candidates must be positive')
    max_depth = int(max_depth)
    max_candidates = int(max_candidates)

    bases: list[Expr] = [Field(name) for name in sorted({_nonempty(name, 'field name') for name in field_names})]
    seen_constants: set[str] = set()
    for value in constants:
        value = _json_scalar(value)
        key = json.dumps(value, sort_keys=True, separators=(',', ':'))
        if key not in seen_constants:
            seen_constants.add(key)
            bases.append(Const(value))

    out: list[Expr] = []
    seen: set[str] = set()
    by_depth: dict[int, list[Expr]] = {}

    def add(expr: Expr) -> bool:
        digest = expr_digest(expr)
        if digest in seen:
            return False
        seen.add(digest)
        out.append(expr)
        by_depth.setdefault(expr.depth, []).append(expr)
        return len(out) >= max_candidates

    for expr in bases:
        if add(expr):
            return tuple(out)

    for depth in range(1, max_depth + 1):
        previous = tuple(expr for expr in out if expr.depth <= depth - 1)
        frontier = tuple(expr for expr in out if expr.depth == depth - 1)
        for arg in frontier:
            for op in _UNARY_OPS:
                if add(Unary(op, arg)):
                    return tuple(out)
        for left in previous:
            for right in previous:
                if max(left.depth, right.depth) != depth - 1:
                    continue
                for op in _BINARY_OPS:
                    if add(Binary(op, left, right)):
                        return tuple(out)
        # Conditionals are intentionally generated last because they have the largest branching factor.
        for condition in previous:
            for when_true in previous:
                for when_false in previous:
                    if max(condition.depth, when_true.depth, when_false.depth) != depth - 1:
                        continue
                    if add(IfElse(condition, when_true, when_false)):
                        return tuple(out)
    return tuple(out)


__all__ = [
    'Expr', 'Field', 'Const', 'Unary', 'Binary', 'IfElse',
    'evaluate_expr', 'expr_digest', 'enumerate_expressions',
]
