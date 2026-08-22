import pytest

from cogcoder.organization.coordination_delivery import AckStatus, DeliveryCoordinator
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind


def test_delivery_and_ack_are_idempotent_and_recipient_bound():
    runtime = OrganizationRuntime.first_generation()
    event = runtime.ledger.append(
        EventKind.CENTRAL_CORRECTION,
        source_agent_id='nolane.central', target_agent_id='coding.backend.01', region='core-coding',
        payload={'directive': 'repair transaction boundary'}, requires_ack=True, priority=100,
    )
    deliveries = DeliveryCoordinator(registry=runtime.registry, events=runtime.ledger)
    first = deliveries.deliver(event.event_id, 'coding.backend.01')
    assert first.ack_status is AckStatus.PENDING
    assert deliveries.deliver(event.event_id, 'coding.backend.01') == first
    with pytest.raises(PermissionError):
        deliveries.acknowledge(first.delivery_id, 'coding.systems.01')
    acked = deliveries.acknowledge(first.delivery_id, 'coding.backend.01')
    assert acked.ack_status is AckStatus.ACKED
    assert deliveries.acknowledge(first.delivery_id, 'coding.backend.01') == acked
    assert runtime.ledger.get(acked.ack_event_id).causal_parent_ids == (event.event_id,)


def test_causal_child_delivery_waits_for_parent_for_same_recipient():
    runtime = OrganizationRuntime.first_generation()
    parent = runtime.ledger.append(
        EventKind.PLAN_CHANGE_PROPOSED, source_agent_id='planning.chief',
        target_agent_id='coding.backend.01', region='core-coding', payload={'change': 'parent'},
    )
    child = runtime.ledger.append(
        EventKind.TASK_PROGRESS, source_agent_id='coding.chief', target_agent_id='coding.backend.01',
        region='core-coding', causal_parent_ids=(parent.event_id,), payload={'change': 'child'},
    )
    deliveries = DeliveryCoordinator(registry=runtime.registry, events=runtime.ledger)
    with pytest.raises(ValueError):
        deliveries.deliver(child.event_id, 'coding.backend.01')
    deliveries.deliver(parent.event_id, 'coding.backend.01')
    assert deliveries.deliver(child.event_id, 'coding.backend.01').event_id == child.event_id


def test_fabricated_event_is_rejected_and_state_round_trip_validates_source():
    runtime = OrganizationRuntime.first_generation()
    deliveries = DeliveryCoordinator(registry=runtime.registry, events=runtime.ledger)
    with pytest.raises(KeyError):
        deliveries.deliver('evt-99999999', 'coding.backend.01')

    event = runtime.ledger.append(
        EventKind.TASK_PROGRESS, source_agent_id='coding.chief', target_agent_id='coding.backend.01',
        region='core-coding', payload={'pct': 10},
    )
    deliveries.deliver(event.event_id, 'coding.backend.01')
    state = deliveries.to_state()
    restored = DeliveryCoordinator.from_state(
        registry=runtime.registry, events=runtime.ledger, state=state,
    )
    assert restored.to_state() == state


def test_central_specialist_action_gives_target_and_chief_same_canonical_event():
    runtime = OrganizationRuntime.first_generation()
    event = runtime.central_action(
        EventKind.CENTRAL_CORRECTION,
        target_agent_id='coding.backend.01', directive='fix retry semantics', evidence_ids=('EV-CENTRAL',),
    )
    receipts = runtime.coordination.deliver_event(event.event_id)
    by_agent = {row.recipient_agent_id: row for row in receipts}
    assert {'coding.backend.01', 'coding.chief'} <= set(by_agent)
    assert by_agent['coding.backend.01'].event_id == by_agent['coding.chief'].event_id == event.event_id
    assert by_agent['coding.backend.01'].source_event_digest == by_agent['coding.chief'].source_event_digest == event.digest
    target = runtime.coordination.acknowledge(by_agent['coding.backend.01'].delivery_id, 'coding.backend.01')
    assert target.ack_status is AckStatus.ACKED
    assert runtime.coordination.delivery_for(event.event_id, 'coding.chief').event_id == event.event_id
