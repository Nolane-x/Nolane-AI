import copy
import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind


def _rich_state_runtime():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-R', title='replay lease', plan_node_id='P-R')
    runtime.coordination.grant_lease('T-R', 'coding.backend.01', token=1, stale_after_tokens=5)
    event = runtime.ledger.append(
        EventKind.CENTRAL_CORRECTION, source_agent_id='nolane.central',
        target_agent_id='coding.backend.01', region='core-coding', requires_ack=True,
        payload={'directive': 'replay-safe correction'},
    )
    receipts = runtime.coordination.deliver_event(event.event_id)
    target = next(row for row in receipts if row.recipient_agent_id == 'coding.backend.01')
    runtime.coordination.acknowledge(target.delivery_id, 'coding.backend.01')
    packet = runtime.coordination.open_conflict(
        'coding.backend.01', 'data-state', proposition='replay migration',
        requested_action='review schema', evidence_refs=('EV-R',),
    )
    runtime.coordination.add_claim(
        packet.conflict_id, 'architecture.api-interface.01', proposition='keep compatibility',
        requested_action='add compatibility test', evidence_refs=('EV-R2',),
    )
    runtime.coordination.plan_wakes(event.event_id)
    return runtime


def test_runtime_coordination_snapshot_round_trip_is_exact():
    runtime = _rich_state_runtime()
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(state)
    assert restored.to_state() == state


def test_old_runtime_state_without_coordination_derives_epoch_one_compatibility_lease():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-OLD', title='legacy leased task', plan_node_id='P-OLD')
    runtime.tasks.lease('T-OLD', 'coding.backend.01')
    state = runtime.to_state()
    state.pop('coordination', None)
    restored = OrganizationRuntime.from_state(state)
    current = restored.coordination.current_lease('T-OLD')
    assert current.agent_id == 'coding.backend.01'
    assert current.epoch == 1
    assert restored.coordination.deliveries() == ()
    assert restored.coordination.conflicts() == ()


def test_lost_delivery_metadata_is_reconciled_from_canonical_ledger():
    runtime = OrganizationRuntime.first_generation()
    event = runtime.ledger.append(
        EventKind.TASK_PROGRESS, source_agent_id='coding.chief', target_agent_id='coding.backend.01',
        region='core-coding', payload={'pct': 50},
    )
    assert runtime.coordination.deliveries() == ()
    rows = runtime.coordination.reconcile_delivery(event.event_id)
    assert len(rows) == 1
    assert rows[0].recipient_agent_id == 'coding.backend.01'
    assert runtime.coordination.reconcile_delivery(event.event_id) == rows


def test_corrupt_delivery_event_and_digest_fail_closed_on_restore():
    runtime = _rich_state_runtime()
    state = runtime.to_state()
    bad_event = copy.deepcopy(state)
    bad_event['coordination']['deliveries']['receipts'][0]['event_id'] = 'evt-99999999'
    with pytest.raises((ValueError, KeyError)):
        OrganizationRuntime.from_state(bad_event)

    bad_digest = copy.deepcopy(state)
    bad_digest['coordination']['leases']['receipts'][0]['digest'] = '0' * 64
    with pytest.raises(ValueError):
        OrganizationRuntime.from_state(bad_digest)


def test_corrupt_double_active_lease_fails_closed():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-DOUBLE', title='double lease corrupt state', plan_node_id='P-D')
    runtime.coordination.grant_lease('T-DOUBLE', 'coding.backend.01', token=0)
    state = runtime.to_state()
    bad = copy.deepcopy(state)
    original = bad['coordination']['leases']['receipts'][0]
    duplicate = dict(original)
    duplicate['lease_id'] = 'lease-99999999'
    duplicate['agent_id'] = 'coding.systems.01'
    duplicate['epoch'] = 2
    bad['coordination']['leases']['receipts'].append(duplicate)
    with pytest.raises(ValueError):
        OrganizationRuntime.from_state(bad)
