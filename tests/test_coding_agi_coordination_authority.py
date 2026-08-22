import pytest

from cogcoder.organization.runtime import OrganizationRuntime


def test_cross_region_proposal_never_silently_writes_authoritative_artifact():
    runtime = OrganizationRuntime.first_generation()
    before_owner = runtime.authority.owner_of('data-state')
    packet = runtime.coordination.propose_cross_region_change(
        proposer_agent_id='coding.backend.01', subject_artifact_id='data-state',
        proposition='transaction code requires a compatible schema field',
        requested_action='add nullable migration field', evidence_refs=('EV-XREGION',),
    )
    assert before_owner == runtime.authority.owner_of('data-state') == 'data.chief'
    assert packet.owner_agent_id == 'data.chief'
    with pytest.raises(PermissionError):
        runtime.authority.require_write('coding.backend.01', 'data-state')
    assert runtime.coordination.delivery_for_owner(packet.conflict_id).recipient_agent_id == 'data.chief'


def test_chief_cannot_suppress_central_delivery_to_its_specialist():
    runtime = OrganizationRuntime.first_generation()
    event = runtime.central_intervene(
        target_agent_id='coding.backend.01', directive='stop unsafe patch', evidence_ids=('EV-STOP',),
    )
    receipts = runtime.coordination.deliver_event(event.event_id)
    target = runtime.coordination.delivery_for(event.event_id, 'coding.backend.01')
    chief = runtime.coordination.delivery_for(event.event_id, 'coding.chief')
    assert target in receipts and chief in receipts
    with pytest.raises(PermissionError):
        runtime.coordination.suppress_delivery(chief.delivery_id, actor_agent_id='coding.chief')
    assert runtime.coordination.delivery_for(event.event_id, 'coding.backend.01') == target
