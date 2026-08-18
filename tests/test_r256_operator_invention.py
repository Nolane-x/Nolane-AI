import copy

import pytest

from cogcoder.r253_external_cognition import CognitiveOperatorRegistry, CognitiveOperatorSpec, ExternalWorkingState
from cogcoder.r255_authority import ActionProposal, AuthorityBoundary, AuthorityEnvelope
from cogcoder.r255_lifecycle import ProcedureLifecycleLedger
from cogcoder.r256_operator_dsl import Binary, Const, Field
from cogcoder.r256_operator_invention import (
    AutonomousOperatorInventionEngine,
    OperatorExample,
    OperatorInventionNeed,
)


def _need(**overrides):
    values = dict(
        objective='invent missing normalizer',
        field_names=('x',),
        output_field='result',
        constants=(0, 1),
        max_depth=2,
        max_candidates=5000,
    )
    values.update(overrides)
    return OperatorInventionNeed(**values)


def _example(name, expected, **context):
    return OperatorExample(name, context, expected)


def test_synthesis_is_deterministic_and_finds_minimum_cost_expression_that_passes_independent_challenge():
    train = (_example('t1', 2, x=1), _example('t2', 4, x=3))
    challenges = (_example('h1', 10, x=9), _example('h2', -2, x=-3))
    a = AutonomousOperatorInventionEngine(CognitiveOperatorRegistry(), ProcedureLifecycleLedger())
    b = AutonomousOperatorInventionEngine(CognitiveOperatorRegistry(), ProcedureLifecycleLedger())
    ra = a.synthesize_and_challenge(_need(), train, challenges)
    rb = b.synthesize_and_challenge(_need(), train, challenges)
    assert ra.passed and rb.passed
    assert ra.candidate is not None and rb.candidate is not None
    assert ra.candidate.expression_digest == rb.candidate.expression_digest
    assert ra.candidate.expression == Binary('add', Field('x'), Const(1))
    assert all(row.passed for row in ra.challenge_results)


def test_empty_challenge_suite_is_rejected_fail_closed():
    engine = AutonomousOperatorInventionEngine(CognitiveOperatorRegistry(), ProcedureLifecycleLedger())
    with pytest.raises(ValueError, match='challenge suite must be non-empty'):
        engine.synthesize_and_challenge(_need(), (_example('t', 1, x=1),), ())


def test_failed_candidate_is_quarantined_when_cegis_is_disabled():
    lifecycle = ProcedureLifecycleLedger()
    engine = AutonomousOperatorInventionEngine(CognitiveOperatorRegistry(), lifecycle)
    receipt = engine.synthesize_and_challenge(
        _need(constants=(1,), max_depth=0),
        (_example('train', 1, x=1),),
        (_example('heldout', 2, x=2),),
        max_cegis_rounds=0,
    )
    assert not receipt.passed
    assert receipt.candidate is not None
    assert receipt.candidate.expression == Const(1)
    assert lifecycle.state(receipt.candidate.expression_digest) == 'quarantined'
    assert 'challenge_failed' in receipt.reason


def test_cegis_adds_failing_challenge_and_refines_overfit_constant_into_general_operator():
    lifecycle = ProcedureLifecycleLedger()
    engine = AutonomousOperatorInventionEngine(CognitiveOperatorRegistry(), lifecycle)
    receipt = engine.synthesize_and_challenge(
        _need(constants=(1,), max_depth=0),
        (_example('train', 1, x=1),),
        (_example('heldout-a', 2, x=2), _example('heldout-b', 7, x=7)),
        max_cegis_rounds=2,
    )
    assert receipt.passed
    assert receipt.cegis_rounds == 1
    assert receipt.candidate is not None
    assert receipt.candidate.expression == Field('x')
    assert receipt.training_examples_used == 2
    assert lifecycle.state(receipt.candidate.expression_digest) == 'probation'


def test_promotion_creates_pure_content_addressed_operator_in_child_registry_only():
    parent = CognitiveOperatorRegistry()
    lifecycle = ProcedureLifecycleLedger()
    engine = AutonomousOperatorInventionEngine(parent, lifecycle)
    receipt = engine.synthesize_and_challenge(
        _need(),
        (_example('t1', 2, x=1), _example('t2', 5, x=4)),
        (_example('h1', 9, x=8),),
    )
    promoted = engine.promote(receipt)
    assert promoted.operator.operator_id.startswith('invented.')
    assert promoted.operator.side_effect_class == 'pure'
    assert not parent.has(promoted.operator.operator_id)
    assert promoted.registry.has(promoted.operator.operator_id)
    assert lifecycle.state(promoted.expression_digest) == 'promoted'


def test_promotion_fails_closed_on_content_addressed_id_collision_with_different_host_operator():
    probe = AutonomousOperatorInventionEngine(CognitiveOperatorRegistry(), ProcedureLifecycleLedger())
    receipt = probe.synthesize_and_challenge(
        _need(),
        (_example('t1', 2, x=1), _example('t2', 4, x=3)),
        (_example('h1', 8, x=7),),
    )
    assert receipt.candidate is not None
    collision_id = f'invented.{receipt.candidate.expression_digest[:20]}'
    host = CognitiveOperatorSpec(
        collision_id, 'host', frozenset({'host'}), frozenset(), frozenset({'other'}),
        0.0, 0.0, 'pure', 'host-v1', 'nolane://host/collision', lambda *_: {'success': True},
    )
    parent = CognitiveOperatorRegistry((host,))
    engine = AutonomousOperatorInventionEngine(parent, ProcedureLifecycleLedger())
    second = engine.synthesize_and_challenge(
        _need(),
        (_example('t1', 2, x=1), _example('t2', 4, x=3)),
        (_example('h1', 8, x=7),),
    )
    with pytest.raises(ValueError, match='operator id collision'):
        engine.promote(second)


def test_live_evaluation_error_rolls_back_public_state_and_terminally_rolls_back_invention():
    lifecycle = ProcedureLifecycleLedger()
    engine = AutonomousOperatorInventionEngine(CognitiveOperatorRegistry(), lifecycle)
    need = _need(field_names=('x', 'y'), constants=(), max_depth=1, max_candidates=5000)
    receipt = engine.synthesize_and_challenge(
        need,
        (_example('t1', 2.0, x=4, y=2), _example('t2', 3.0, x=9, y=3)),
        (_example('h1', 2.5, x=10, y=4),),
    )
    assert receipt.passed and receipt.candidate is not None
    assert receipt.candidate.expression == Binary('div', Field('x'), Field('y'))
    promoted = engine.promote(receipt)
    state = ExternalWorkingState(context={'x': 5, 'y': 0, 'keep': {'nested': [1, 2]}})
    before = copy.deepcopy(state)
    live = engine.execute_promoted(promoted.operator.operator_id, state)
    assert not live.success and live.rolled_back
    assert state == before
    assert lifecycle.state(promoted.expression_digest) == 'rolled_back'


def test_invention_does_not_widen_preissued_host_authority():
    engine = AutonomousOperatorInventionEngine(CognitiveOperatorRegistry(), ProcedureLifecycleLedger())
    receipt = engine.synthesize_and_challenge(
        _need(),
        (_example('t1', 2, x=1), _example('t2', 3, x=2)),
        (_example('h1', 7, x=6),),
    )
    promoted = engine.promote(receipt)
    envelope = AuthorityEnvelope.issue(
        objective='repair safely',
        allowed_actions=('existing.safe',),
        allowed_side_effect_classes=('pure',),
        issuer='host:test',
    )
    decision = AuthorityBoundary().authorize(envelope, ActionProposal(
        promoted.operator.operator_id, promoted.operator.side_effect_class,
        'inventor', 'nolane://invented',
    ))
    assert not decision.allowed
    assert decision.reason == 'action_not_pre_authorized'
