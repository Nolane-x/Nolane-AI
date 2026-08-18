import pytest

from cogcoder.r256_operator_dsl import Binary, Const, Field, Unary, evaluate_expr
from cogcoder.r257_vocabulary import (
    AbstractionCall,
    CognitiveVocabulary,
    LearnedAbstraction,
    TemplateParam,
    evaluate_with_vocabulary,
    expand_expr,
    make_abstraction,
)


def _clamp_abstraction():
    p0, p1, p2 = TemplateParam(0), TemplateParam(1), TemplateParam(2)
    return make_abstraction(
        Binary('min', Binary('max', p0, p1), p2),
        parameter_count=3,
        support_task_ids=('t1', 't2', 't3'),
        raw_occurrence_cost=18,
        rewritten_cost=14,
    )


def test_parameterized_abstraction_expands_and_evaluates_like_r256():
    abstraction = _clamp_abstraction()
    vocab = CognitiveVocabulary((abstraction,))
    call = AbstractionCall(abstraction.abstraction_id, (Field('x'), Field('lo'), Field('hi')))
    expanded = expand_expr(call, vocab)
    assert expanded.to_data() == Binary('min', Binary('max', Field('x'), Field('lo')), Field('hi')).to_data()
    for ctx in ({'x': -5, 'lo': 0, 'hi': 10}, {'x': 7, 'lo': 0, 'hi': 10}, {'x': 99, 'lo': 0, 'hi': 10}):
        assert evaluate_with_vocabulary(call, ctx, vocab) == evaluate_expr(expanded, ctx)


def test_content_digest_is_independent_of_support_task_order():
    a = _clamp_abstraction()
    b = make_abstraction(
        a.template,
        parameter_count=3,
        support_task_ids=('t3', 't1', 't2'),
        raw_occurrence_cost=18,
        rewritten_cost=14,
    )
    assert a.abstraction_id == b.abstraction_id
    assert a.compression_gain == 4


def test_missing_call_argument_is_rejected():
    abstraction = _clamp_abstraction()
    vocab = CognitiveVocabulary((abstraction,))
    with pytest.raises(ValueError, match='argument count'):
        expand_expr(AbstractionCall(abstraction.abstraction_id, (Field('x'),)), vocab)


def test_unknown_and_recursive_abstractions_fail_closed():
    with pytest.raises(KeyError):
        expand_expr(AbstractionCall('missing', (Field('x'),)), CognitiveVocabulary())

    recursive = LearnedAbstraction(
        abstraction_id='loop',
        parameter_count=1,
        template=AbstractionCall('loop', (TemplateParam(0),)),
        support_task_ids=('a', 'b', 'c'),
        raw_occurrence_cost=20,
        rewritten_cost=10,
    )
    with pytest.raises(ValueError, match='cycle|recursive'):
        CognitiveVocabulary((recursive,))


def test_expansion_budget_rejects_nested_growth():
    identity = make_abstraction(
        Unary('abs', TemplateParam(0)),
        parameter_count=1,
        support_task_ids=('a', 'b', 'c'),
        raw_occurrence_cost=12,
        rewritten_cost=8,
    )
    vocab = CognitiveVocabulary((identity,))
    expr = Field('x')
    for _ in range(8):
        expr = AbstractionCall(identity.abstraction_id, (expr,))
    with pytest.raises(ValueError, match='expansion'):
        expand_expr(expr, vocab, max_expansion_nodes=6)
