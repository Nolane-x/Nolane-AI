import pytest

from cogcoder.organization.authority import AuthorityGraph
from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.events import EventLedger
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.types import EventKind


def _registry():
    return AgentRegistry(build_first_generation_blueprint())


def test_artifact_owner_is_authoritative_and_central_override_is_explicit():
    registry = _registry()
    authority = AuthorityGraph(registry)
    authority.claim_owner('master-plan', 'planning.chief')

    assert authority.can_write('planning.chief', 'master-plan') is True
    assert authority.can_write('coding.backend.01', 'master-plan') is False
    with pytest.raises(PermissionError, match='not authorized'):
        authority.require_write('coding.backend.01', 'master-plan')

    authority.record_block('master-plan', 'verification.chief', reason='acceptance contract failed')
    with pytest.raises(PermissionError, match='blocked'):
        authority.require_write('planning.chief', 'master-plan')

    receipt = authority.central_override(
        artifact_id='master-plan',
        reason='restore globally consistent plan after verified correction',
        evidence_ids=('EV-1',),
    )
    assert receipt.actor_agent_id == 'nolane.central'
    assert receipt.overrode_block is True
    assert authority.can_write('nolane.central', 'master-plan', override_id=receipt.override_id) is True


def test_typed_event_ledger_is_append_only_ordered_and_routes_central_intervention_to_chief():
    ledger = EventLedger()
    ledger.subscribe('debug.chief', EventKind.CENTRAL_INTERVENTION, region='debugging-failure')
    ledger.subscribe('debug.runtime-trace.01', EventKind.CENTRAL_INTERVENTION)

    first = ledger.append(
        EventKind.CENTRAL_INTERVENTION,
        source_agent_id='nolane.central',
        target_agent_id='debug.runtime-trace.01',
        region='debugging-failure',
        payload={'directive': 're-evaluate H17', 'evidence': ['trace-9']},
    )
    second = ledger.append(
        EventKind.TEST_FAILED,
        source_agent_id='verification.integration-e2e.01',
        region='verification-testing',
        payload={'test': 'integration-18'},
    )

    assert first.event_id == 'evt-00000001'
    assert second.event_id == 'evt-00000002'
    assert first.digest != second.digest
    assert ledger.events_since(first.event_id) == (second,)

    chief_events = ledger.deliverable_for('debug.chief')
    worker_events = ledger.deliverable_for('debug.runtime-trace.01')
    assert first in chief_events
    assert first in worker_events

    restored = EventLedger.from_state(ledger.to_state())
    assert restored.events_since(None) == ledger.events_since(None)
