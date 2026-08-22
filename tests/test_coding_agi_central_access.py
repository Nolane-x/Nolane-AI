import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.central_access import CentralCoreAccessPolicy


def test_central_cannot_silently_take_private_region_core():
    runtime = OrganizationRuntime.first_generation()
    policy = CentralCoreAccessPolicy(runtime.registry, runtime.external_cores)

    assert policy.can_invoke('global-project-graph', token=1)
    assert not policy.can_invoke('runtime-tracer', token=1)

    lease = policy.grant_lease(
        core_id='runtime-tracer',
        owner='debugging-failure',
        call_budget=2,
        expires_at_token=10,
        reason='cross-region incident',
        evidence_refs=('ev-core-1',),
    )
    assert policy.can_invoke('runtime-tracer', token=2, lease_id=lease.lease_id)
    first = policy.consume(lease.lease_id, token=2)
    assert first.remaining_calls == 1
    second = policy.consume(lease.lease_id, token=3)
    assert second.remaining_calls == 0
    assert not policy.can_invoke('runtime-tracer', token=4, lease_id=lease.lease_id)
    with pytest.raises(PermissionError):
        policy.consume(lease.lease_id, token=4)


def test_core_lease_owner_expiry_and_revoke_are_fail_closed():
    runtime = OrganizationRuntime.first_generation()
    policy = CentralCoreAccessPolicy(runtime.registry, runtime.external_cores)

    with pytest.raises(PermissionError):
        policy.grant_lease(
            core_id='runtime-tracer',
            owner='core-coding',
            call_budget=1,
            expires_at_token=10,
            reason='wrong owner',
            evidence_refs=('ev-core-2',),
        )

    lease = policy.grant_lease(
        core_id='runtime-tracer',
        owner='debugging-failure',
        call_budget=1,
        expires_at_token=5,
        reason='bounded debug trace',
        evidence_refs=('ev-core-3',),
    )
    assert not policy.can_invoke('runtime-tracer', token=6, lease_id=lease.lease_id)
    revoked = policy.revoke(lease.lease_id, reason='incident closed', evidence_refs=('ev-core-4',))
    assert revoked.revoked
    assert not policy.can_invoke('runtime-tracer', token=2, lease_id=lease.lease_id)

    restored = CentralCoreAccessPolicy.from_state(runtime.registry, runtime.external_cores, policy.to_state())
    assert restored.to_state() == policy.to_state()
