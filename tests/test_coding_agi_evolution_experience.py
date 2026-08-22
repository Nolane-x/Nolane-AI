import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.events import EventLedger
from cogcoder.organization.experience import ExperienceLedger, ExperienceOutcome, LearningLayer
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.types import EvidenceRecord


def _ledger():
    registry = AgentRegistry(build_first_generation_blueprint())
    return registry, ExperienceLedger(registry=registry, events=EventLedger())


def test_every_identity_records_only_its_own_immutable_experience():
    _, ledger = _ledger()
    row = ledger.record(
        agent_id='coding.backend.01', author_agent_id='coding.backend.01',
        domain='backend-retry', outcome=ExperienceOutcome.SUCCESS,
        summary='idempotent retry eliminated duplicate writes', task_id='T-1',
        object_refs=('src/retry.py',), evidence_refs=('EV-EXP',),
    )
    assert row.agent_id == 'coding.backend.01'
    assert ledger.get(row.experience_id) == row
    duplicate = ledger.record(
        agent_id='coding.backend.01', author_agent_id='coding.backend.01',
        domain='backend-retry', outcome=ExperienceOutcome.SUCCESS,
        summary='idempotent retry eliminated duplicate writes', task_id='T-1',
        object_refs=('src/retry.py',), evidence_refs=('EV-EXP',),
    )
    assert duplicate.experience_id == row.experience_id
    with pytest.raises(PermissionError):
        ledger.record(
            agent_id='coding.backend.01', author_agent_id='debug.chief', domain='backend-retry',
            outcome=ExperienceOutcome.FAILURE, summary='fabricated on behalf of coder', task_id='T-1',
            object_refs=('src/retry.py',), evidence_refs=('EV-X',),
        )


def test_positive_attribution_requires_clean_external_evidence_and_dirty_evidence_is_preserved_negative():
    _, ledger = _ledger()
    experience = ledger.record(
        agent_id='coding.backend.01', author_agent_id='coding.backend.01',
        domain='backend-retry', outcome=ExperienceOutcome.MIXED,
        summary='retry strategy needs attribution', task_id='T-2', object_refs=('retry',), evidence_refs=('EV-EXP-2',),
    )
    with pytest.raises(PermissionError):
        ledger.attribute(
            experience.experience_id, learning_layer=LearningLayer.STRATEGY,
            lesson='use bounded retry', evidence=EvidenceRecord('EV-SELF', 'coding.backend.01', True),
        )
    positive = ledger.attribute(
        experience.experience_id, learning_layer=LearningLayer.STRATEGY,
        lesson='use bounded retry with idempotency',
        evidence=EvidenceRecord('EV-EXT', 'verification.integration-e2e.01', True),
    )
    assert positive.positive is True
    negative = ledger.attribute(
        experience.experience_id, learning_layer=LearningLayer.STRATEGY,
        lesson='retry forever',
        evidence=EvidenceRecord('EV-BAD', 'verification.fuzz-regression.01', False, regressions=1),
    )
    assert negative.positive is False
    assert ledger.get_attribution(negative.attribution_id) == negative
    state = ledger.to_state()
    restored = ExperienceLedger.from_state(registry=ledger.registry, events=ledger.events, state=state)
    assert restored.to_state() == state
