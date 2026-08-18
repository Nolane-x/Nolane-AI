import pytest

from cogcoder.r256_operator_dsl import (
    Binary,
    Const,
    Field,
    IfElse,
    Unary,
    evaluate_expr,
    expr_digest,
    enumerate_expressions,
)


def test_expression_digest_is_canonical_and_stable():
    left = Binary('add', Field('x'), Const(2))
    right = Binary('add', Field('x'), Const(2))
    different = Binary('sub', Field('x'), Const(2))
    assert left.to_data() == {'op': 'add', 'left': {'field': 'x'}, 'right': {'const': 2}}
    assert expr_digest(left) == expr_digest(right)
    assert expr_digest(left) != expr_digest(different)


def test_evaluator_is_deterministic_for_numeric_string_boolean_and_conditional_ops():
    expr = IfElse(
        Binary('gt', Field('score'), Const(10)),
        Unary('lower', Unary('strip', Field('name'))),
        Const('fallback'),
    )
    context = {'score': 11, 'name': '  ALPHA  '}
    assert evaluate_expr(expr, context) == 'alpha'
    assert evaluate_expr(expr, context) == 'alpha'


def test_guarded_division_rejects_zero_denominator_instead_of_hiding_failure():
    expr = Binary('div', Field('numerator'), Field('denominator'))
    with pytest.raises(ValueError, match='division by zero'):
        evaluate_expr(expr, {'numerator': 4, 'denominator': 0})


def test_closed_opcode_table_rejects_effectful_or_dynamic_operations():
    with pytest.raises(ValueError, match='unsupported unary op'):
        Unary('import', Field('x'))
    with pytest.raises(ValueError, match='unsupported binary op'):
        Binary('exec', Field('x'), Const('whoami'))


def test_runtime_type_checks_reject_nonsensical_operations():
    with pytest.raises(TypeError, match='numeric'):
        evaluate_expr(Binary('mul', Field('x'), Const(2)), {'x': 'abc'})
    with pytest.raises(TypeError, match='string'):
        evaluate_expr(Unary('lower', Field('x')), {'x': 7})


def test_expression_enumeration_is_bounded_deterministic_and_deduplicated():
    a = enumerate_expressions(('x', 'y'), constants=(0, 1), max_depth=2, max_candidates=80)
    b = enumerate_expressions(('x', 'y'), constants=(0, 1), max_depth=2, max_candidates=80)
    assert [expr_digest(x) for x in a] == [expr_digest(x) for x in b]
    assert len(a) <= 80
    assert len({expr_digest(x) for x in a}) == len(a)
    assert Field('x') in a and Const(1) in a
