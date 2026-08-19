from __future__ import annotations

from dataclasses import dataclass

from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary, expr_digest


_PROBE_ROLES = ('__p0', '__p1', '__p2')


def _used_fields(expr: Expr) -> frozenset[str]:
    if isinstance(expr, Field):
        return frozenset((expr.name,))
    if isinstance(expr, Const):
        return frozenset()
    if isinstance(expr, Unary):
        return _used_fields(expr.arg)
    if isinstance(expr, Binary):
        return _used_fields(expr.left) | _used_fields(expr.right)
    if isinstance(expr, IfElse):
        return (
            _used_fields(expr.condition)
            | _used_fields(expr.when_true)
            | _used_fields(expr.when_false)
        )
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')


@dataclass(frozen=True, slots=True)
class PortableCausalProgram:
    expression: Expr
    expression_digest: str
    probe_roles: tuple[str, str, str] = _PROBE_ROLES
    trainable_parameter_count: int = 0

    def to_data(self) -> dict[str, object]:
        return {
            'schema_version': 1,
            'capability': 'portable-three-probe-causal-program',
            'probe_roles': list(self.probe_roles),
            'expression': self.expression.to_data(),
            'expression_digest': self.expression_digest,
            'trainable_parameter_count': self.trainable_parameter_count,
        }


def export_expression_prior(expression: Expr) -> PortableCausalProgram:
    if not isinstance(expression, Expr):
        raise TypeError('expression must be Expr')
    used = _used_fields(expression)
    if used != frozenset(_PROBE_ROLES):
        raise ValueError('expression must depend on exactly three abstract probe roles')
    return PortableCausalProgram(
        expression=expression,
        expression_digest=expr_digest(expression),
    )
