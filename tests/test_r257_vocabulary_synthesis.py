import copy

from cogcoder.r253_external_cognition import ExternalWorkingState
from cogcoder.r255_lifecycle import ProcedureLifecycleLedger
from cogcoder.r256_operator_dsl import Binary, Field, Unary
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r257_library_learning import VerifiedExpression, learn_abstractions, promote_abstraction
from cogcoder.r257_vocabulary import CognitiveVocabulary
from cogcoder.r257_vocabulary_synthesis import (
    execute_with_live_verification,
    synthesize_base_with_budget,
    synthesize_with_vocabulary,
)


def clamp_expr(x, lo, hi):
    return Binary('min', Binary('max', Field(x), Field(lo)), Field(hi))


def _learn_clamp():
    corpus = [VerifiedExpression(f'c{i}', clamp_expr(f'x{i}', f'l{i}', f'h{i}')) for i in range(6)]
    candidate = learn_abstractions(corpus).candidates[0]
    lifecycle = ProcedureLifecycleLedger()
    vocab = CognitiveVocabulary()
    assert promote_abstraction(
        candidate,
        [VerifiedExpression('held1', clamp_expr('q', 'a', 'b')), VerifiedExpression('held2', clamp_expr('z', 'u', 'v'))],
        vocabulary=vocab,
        lifecycle=lifecycle,
    )
    return candidate, vocab, lifecycle


def test_learned_vocabulary_solves_composition_under_depth_budget_that_base_cannot():
    _candidate, vocab, _lifecycle = _learn_clamp()
    need = OperatorInventionNeed('opaque composed target', ('x', 'lo', 'hi'), 'out', constants=(), max_depth=2, max_candidates=6000)
    examples = (
        OperatorExample('a', {'x': -5, 'lo': 0, 'hi': 10}, 0),
        OperatorExample('b', {'x': 4, 'lo': 0, 'hi': 10}, 4),
        OperatorExample('c', {'x': -7, 'lo': -3, 'hi': 2}, 3),
        OperatorExample('d', {'x': 9, 'lo': -3, 'hi': 2}, 2),
    )
    # Target behavior is abs(clamp(x, lo, hi)); the first two cases alone are not enough to distinguish it.
    examples = examples + (
        OperatorExample('e', {'x': -2, 'lo': -5, 'hi': 8}, 2),
        OperatorExample('f', {'x': 7, 'lo': -5, 'hi': 8}, 7),
    )
    base = synthesize_base_with_budget(need, examples)
    grown = synthesize_with_vocabulary(need, examples, vocab)
    assert not base.passed
    assert grown.passed
    assert grown.expression is not None
    assert grown.expression.depth <= 2
    assert grown.search_evaluations <= need.max_candidates * len(examples)
    assert grown.used_abstraction_ids == tuple(a.abstraction_id for a in vocab.abstractions())


def test_live_counterexample_revokes_abstraction_and_restores_state():
    candidate, vocab, lifecycle = _learn_clamp()
    need = OperatorInventionNeed('opaque composed target', ('x', 'lo', 'hi'), 'out', constants=(), max_depth=2, max_candidates=6000)
    examples = (
        OperatorExample('a', {'x': -5, 'lo': 0, 'hi': 10}, 0),
        OperatorExample('b', {'x': -2, 'lo': -5, 'hi': 8}, 2),
        OperatorExample('c', {'x': 7, 'lo': -5, 'hi': 8}, 7),
        OperatorExample('d', {'x': 99, 'lo': 0, 'hi': 10}, 10),
    )
    grown = synthesize_with_vocabulary(need, examples, vocab)
    assert grown.passed and grown.expression is not None
    state = ExternalWorkingState(context={'x': 4, 'lo': 0, 'hi': 10, 'sentinel': {'keep': [1, 2]}})
    before = copy.deepcopy(state)
    receipt = execute_with_live_verification(
        grown.expression,
        state,
        output_field='out',
        expected=999,
        vocabulary=vocab,
        lifecycle=lifecycle,
    )
    assert not receipt.success and receipt.rolled_back
    assert state == before
    assert lifecycle.state(candidate.abstraction.abstraction_id) == 'rolled_back'
    assert vocab.abstractions() == ()


def test_verified_seed_is_reused_before_reenumerating_lower_search_layers():
    _candidate, vocab, _lifecycle = _learn_clamp()
    first_need = OperatorInventionNeed('learn bounded intermediate', ('x', 'lo', 'hi'), 'mid', constants=(), max_depth=1, max_candidates=500)
    first_examples = (
        OperatorExample('a', {'x': -5, 'lo': 0, 'hi': 10}, 0),
        OperatorExample('b', {'x': 4, 'lo': 0, 'hi': 10}, 4),
        OperatorExample('c', {'x': 99, 'lo': 0, 'hi': 10}, 10),
    )
    first = synthesize_with_vocabulary(first_need, first_examples, vocab)
    assert first.passed and first.expression is not None

    second_need = OperatorInventionNeed('reuse verified intermediate', ('x', 'lo', 'hi'), 'out', constants=(), max_depth=2, max_candidates=80)
    second_examples = (
        OperatorExample('a', {'x': -5, 'lo': 0, 'hi': 10}, 0),
        OperatorExample('b', {'x': -4, 'lo': -5, 'hi': 10}, 4),
        OperatorExample('c', {'x': 99, 'lo': -3, 'hi': 2}, 2),
    )
    seeded = synthesize_with_vocabulary(second_need, second_examples, vocab, seed_expressions=(first.expression,))
    assert seeded.passed
    assert seeded.expression is not None
    assert seeded.candidates_considered <= second_need.max_candidates
