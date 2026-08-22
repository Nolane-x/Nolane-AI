import pytest

from cogcoder.organization.runtime import OrganizationRuntime


def test_cross_region_disagreement_is_structured_and_owner_resolves():
    runtime = OrganizationRuntime.first_generation()
    packet = runtime.coordination.open_conflict(
        'coding.backend.01', 'data-state',
        proposition='migration needs an idempotency column',
        requested_action='add schema migration', evidence_refs=('EV-MIGRATION',),
    )
    assert packet.owner_agent_id == 'data.chief'
    assert packet.status.value == 'open'
    with pytest.raises(PermissionError):
        runtime.authority.require_write('coding.backend.01', 'data-state')
    with pytest.raises(PermissionError):
        runtime.coordination.resolve_conflict(
            packet.conflict_id, 'architecture.chief', decision='approve', evidence_refs=('EV-A',),
        )
    receipt = runtime.coordination.resolve_conflict(
        packet.conflict_id, 'data.chief', decision='approve migration', evidence_refs=('EV-DATA',),
    )
    assert receipt.resolver_agent_id == 'data.chief'
    assert runtime.coordination.conflict(packet.conflict_id).status.value == 'resolved'


def test_identical_claim_is_idempotent_and_resolved_packet_is_immutable():
    runtime = OrganizationRuntime.first_generation()
    packet = runtime.coordination.open_conflict(
        'coding.backend.01', 'data-state', proposition='cache key must include tenant',
        requested_action='change cache schema', evidence_refs=('EV-CACHE',),
    )
    first = runtime.coordination.add_claim(
        packet.conflict_id, 'architecture.api-interface.01', proposition='cache key must include tenant',
        requested_action='change cache schema', evidence_refs=('EV-CACHE-2',),
    )
    duplicate = runtime.coordination.add_claim(
        packet.conflict_id, 'architecture.api-interface.01', proposition='cache key must include tenant',
        requested_action='change cache schema', evidence_refs=('EV-CACHE-2',),
    )
    assert duplicate == first
    runtime.coordination.resolve_conflict(
        packet.conflict_id, 'data.chief', decision='approve', evidence_refs=('EV-RESOLVE',),
    )
    with pytest.raises(ValueError):
        runtime.coordination.add_claim(
            packet.conflict_id, 'coding.systems.01', proposition='late claim',
            requested_action='reopen silently', evidence_refs=('EV-LATE',),
        )


def test_blocked_artifact_requires_explicit_central_override_for_resolution():
    runtime = OrganizationRuntime.first_generation()
    runtime.authority.record_block('data-state', 'verification.chief', reason='migration evidence incomplete')
    packet = runtime.coordination.open_conflict(
        'coding.backend.01', 'data-state', proposition='urgent compatibility migration',
        requested_action='proceed', evidence_refs=('EV-URGENT',),
    )
    with pytest.raises(PermissionError):
        runtime.coordination.resolve_conflict(
            packet.conflict_id, 'nolane.central', decision='force proceed', evidence_refs=('EV-C',),
        )
    override = runtime.authority.central_override(
        artifact_id='data-state', reason='explicit emergency override', evidence_ids=('EV-C', 'EV-RISK'),
    )
    receipt = runtime.coordination.resolve_conflict(
        packet.conflict_id, 'nolane.central', decision='proceed with override',
        evidence_refs=('EV-C', 'EV-RISK'), override_id=override.override_id,
    )
    assert receipt.override_id == override.override_id
