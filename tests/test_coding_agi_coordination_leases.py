import pytest

from cogcoder.organization.coordination_leases import LeaseCoordinator
from cogcoder.organization.runtime import OrganizationRuntime


def _lease_coord():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-LEASE', title='exclusive mutation', plan_node_id='P-LEASE')
    return runtime, LeaseCoordinator(registry=runtime.registry, tasks=runtime.tasks, events=runtime.ledger)


def test_task_has_one_active_epoch_and_transfer_requires_revoke():
    runtime, leases = _lease_coord()
    first = leases.grant('T-LEASE', 'coding.backend.01', token=1, stale_after_tokens=3)
    assert first.epoch == 1
    assert first.status.value == 'active'
    assert leases.grant('T-LEASE', 'coding.backend.01', token=1, stale_after_tokens=3) == first
    with pytest.raises(ValueError):
        leases.grant('T-LEASE', 'coding.systems.01', token=1, stale_after_tokens=3)

    revoked = leases.revoke(
        'T-LEASE', 'coding.chief', reason='reassign after failed approach', evidence_refs=('EV-LEASE',),
    )
    assert revoked.lease_id == first.lease_id
    assert revoked.status.value == 'revoked'
    second = leases.grant('T-LEASE', 'coding.systems.01', token=2, stale_after_tokens=3)
    assert second.epoch == 2
    assert second.supersedes_lease_id == first.lease_id
    assert runtime.tasks.get('T-LEASE').leased_to == 'coding.systems.01'

    with pytest.raises(PermissionError):
        leases.complete(
            'T-LEASE', 'coding.backend.01', lease_id=first.lease_id, epoch=first.epoch,
            output_artifact_ids=('ART-STALE',),
        )
    completed = leases.complete(
        'T-LEASE', 'coding.systems.01', lease_id=second.lease_id, epoch=second.epoch,
        output_artifact_ids=('ART-GOOD',),
    )
    assert completed.completed_by == 'coding.systems.01'


def test_revoke_authority_is_central_or_own_region_chief_not_specialist():
    _, leases = _lease_coord()
    leases.grant('T-LEASE', 'coding.backend.01', token=0)
    with pytest.raises(PermissionError):
        leases.revoke('T-LEASE', 'data.chief', reason='wrong region', evidence_refs=('EV-X',))
    with pytest.raises(PermissionError):
        leases.revoke('T-LEASE', 'coding.refactor.01', reason='peer revoke', evidence_refs=('EV-X',))
    revoked = leases.revoke('T-LEASE', 'nolane.central', reason='global correction', evidence_refs=('EV-C',))
    assert revoked.status.value == 'revoked'


def test_heartbeat_requires_current_holder_epoch_and_stale_detection_is_non_destructive():
    runtime, leases = _lease_coord()
    active = leases.grant('T-LEASE', 'coding.backend.01', token=3, stale_after_tokens=4)
    renewed = leases.heartbeat(
        'T-LEASE', 'coding.backend.01', lease_id=active.lease_id, epoch=active.epoch, token=5,
    )
    assert renewed.last_heartbeat_token == 5
    assert renewed.renewal_count == 1
    with pytest.raises(PermissionError):
        leases.heartbeat('T-LEASE', 'coding.systems.01', lease_id=active.lease_id, epoch=active.epoch, token=6)
    assert leases.detect_stale(8) == ()
    stale = leases.detect_stale(9)
    assert len(stale) == 1
    assert stale[0].agent_id == 'coding.backend.01'
    assert runtime.tasks.get('T-LEASE').leased_to == 'coding.backend.01'


def test_lease_state_round_trip_is_exact():
    runtime, leases = _lease_coord()
    leases.grant('T-LEASE', 'coding.backend.01', token=2, stale_after_tokens=5)
    state = leases.to_state()
    restored = LeaseCoordinator.from_state(
        registry=runtime.registry, tasks=runtime.tasks, events=runtime.ledger, state=state,
    )
    assert restored.to_state() == state
