import pytest

from cogcoder.r255_lifecycle import ProcedureLifecycleLedger
from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r257_library_learning import (
    AbstractionCandidate,
    VerifiedExpression,
    learn_abstractions,
    match_abstraction,
    promote_abstraction,
)
from cogcoder.r257_vocabulary import CognitiveVocabulary, LearnedAbstraction, TemplateParam


def clamp_expr(x, lo, hi):
    return Binary('min', Binary('max', Field(x), Field(lo)), Field(hi))


def lerp_expr(a, b, t):
    return Binary('add', Field(a), Binary('mul', Field(t), Binary('sub', Field(b), Field(a))))


def test_learns_parameterized_multi_task_abstractions_with_positive_compression():
    corpus = []
    for i in range(6):
        corpus.append(VerifiedExpression(f'c{i}', clamp_expr(f'x{i}', f'l{i}', f'h{i}')))
        corpus.append(VerifiedExpression(f'l{i}', lerp_expr(f'a{i}', f'b{i}', f't{i}')))
    receipt = learn_abstractions(corpus, min_support_tasks=3, min_subexpr_cost=3)
    assert receipt.candidates
    assert all(c.abstraction.compression_gain > 0 for c in receipt.candidates)
    clamp = next(c for c in receipt.candidates if c.support_task_ids == tuple(f'c{i}' for i in range(6)))
    assert len(clamp.support_task_ids) == 6
    args = match_abstraction(clamp.abstraction, clamp_expr('v', 'mn', 'mx'))
    assert [a.to_data() for a in args] == [Field('v').to_data(), Field('mn').to_data(), Field('mx').to_data()]


def test_repeated_variable_equality_pattern_is_preserved():
    corpus = [VerifiedExpression(f't{i}', Binary('add', Field(f'x{i}'), Field(f'x{i}'))) for i in range(6)]
    receipt = learn_abstractions(corpus, min_support_tasks=3, min_subexpr_cost=3)
    candidate = receipt.candidates[0]
    data = candidate.abstraction.template.to_data()
    assert data['left'] == {'param': 0}
    assert data['right'] == {'param': 0}
    assert candidate.abstraction.parameter_count == 1
    assert match_abstraction(candidate.abstraction, Binary('add', Field('a'), Field('b'))) is None


def test_support_is_counted_by_distinct_task_and_noncompressive_groups_are_dropped():
    one_task = [VerifiedExpression('same', clamp_expr(f'x{i}', f'l{i}', f'h{i}')) for i in range(20)]
    assert learn_abstractions(one_task, min_support_tasks=3, min_subexpr_cost=3).candidates == ()
    only_three = [VerifiedExpression(f't{i}', clamp_expr(f'x{i}', f'l{i}', f'h{i}')) for i in range(3)]
    assert learn_abstractions(only_three, min_support_tasks=3, min_subexpr_cost=3).candidates == ()


def test_candidate_ranking_is_deterministic():
    corpus = []
    for i in range(7):
        corpus.extend([
            VerifiedExpression(f'c{i}', clamp_expr(f'x{i}', f'l{i}', f'h{i}')),
            VerifiedExpression(f'l{i}', lerp_expr(f'a{i}', f'b{i}', f't{i}')),
        ])
    a = learn_abstractions(corpus)
    b = learn_abstractions(tuple(reversed(corpus)))
    assert [c.abstraction.abstraction_id for c in a.candidates] == [c.abstraction.abstraction_id for c in b.candidates]
    assert [c.compression_gain for c in a.candidates] == [c.compression_gain for c in b.candidates]


def test_promotion_requires_exact_challenge_and_quarantines_bad_candidate():
    corpus = [VerifiedExpression(f't{i}', clamp_expr(f'x{i}', f'l{i}', f'h{i}')) for i in range(6)]
    candidate = learn_abstractions(corpus).candidates[0]
    lifecycle = ProcedureLifecycleLedger()
    vocab = CognitiveVocabulary()
    promoted = promote_abstraction(
        candidate,
        [VerifiedExpression('held1', clamp_expr('v', 'lo', 'hi')), VerifiedExpression('held2', clamp_expr('q', 'a', 'b'))],
        vocabulary=vocab,
        lifecycle=lifecycle,
    )
    assert promoted
    assert vocab.get(candidate.abstraction.abstraction_id) == candidate.abstraction
    assert lifecycle.state(candidate.abstraction.abstraction_id) == 'promoted'

    bad_abs = LearnedAbstraction(
        'bad', 3,
        Binary('max', Binary('min', TemplateParam(0), TemplateParam(1)), TemplateParam(2)),
        ('x1', 'x2', 'x3', 'x4'), 40, 20,
    )
    bad = AbstractionCandidate(bad_abs, ('x1', 'x2', 'x3', 'x4'), 20)
    bad_lifecycle = ProcedureLifecycleLedger()
    assert not promote_abstraction(
        bad,
        [VerifiedExpression('held', clamp_expr('v', 'lo', 'hi'))],
        vocabulary=CognitiveVocabulary(),
        lifecycle=bad_lifecycle,
    )
    assert bad_lifecycle.state('bad') == 'quarantined'
