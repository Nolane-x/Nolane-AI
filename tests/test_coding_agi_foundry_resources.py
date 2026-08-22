import pytest

from cogcoder.organization.foundry_resources import (
    FoundryBudget,
    FoundryResourceGovernor,
    FoundryResourceKind,
)


def _budget(max_workers=4):
    return FoundryBudget(
        compute_units=10, tool_calls=3, external_core_calls=2,
        max_workers=max_workers, lifetime_tokens=20,
    )


def test_budget_is_positive_and_usage_is_identity_bound_and_fail_closed():
    with pytest.raises(ValueError):
        FoundryBudget(compute_units=0, tool_calls=1, external_core_calls=1, max_workers=1, lifetime_tokens=1)
    governor = FoundryResourceGovernor()
    governor.register_manifest('ephemeral-1', team_id='team-a', sponsor_agent_id='coding.chief', budget=_budget())
    governor.reserve_active('ephemeral-1')
    row = governor.consume('ephemeral-1', FoundryResourceKind.COMPUTE, 4, actor_ephemeral_id='ephemeral-1')
    assert row.units == 4
    assert governor.remaining('ephemeral-1', FoundryResourceKind.COMPUTE) == 6
    with pytest.raises(PermissionError):
        governor.consume('ephemeral-1', FoundryResourceKind.TOOL_CALL, 1, actor_ephemeral_id='ephemeral-other')
    governor.consume('ephemeral-1', FoundryResourceKind.TOOL_CALL, 3, actor_ephemeral_id='ephemeral-1')
    with pytest.raises(PermissionError):
        governor.consume('ephemeral-1', FoundryResourceKind.TOOL_CALL, 1, actor_ephemeral_id='ephemeral-1')
    assert governor.remaining('ephemeral-1', FoundryResourceKind.TOOL_CALL) == 0


def test_team_sponsor_and_organization_concurrency_caps_are_enforced():
    governor = FoundryResourceGovernor()
    for index in range(4):
        eid = f'ephemeral-team-{index}'
        governor.register_manifest(eid, team_id='team-a', sponsor_agent_id='coding.chief', budget=_budget(max_workers=4))
        governor.reserve_active(eid)
    governor.register_manifest('ephemeral-team-over', team_id='team-a', sponsor_agent_id='coding.chief', budget=_budget(max_workers=4))
    with pytest.raises(PermissionError):
        governor.reserve_active('ephemeral-team-over')

    sponsor = FoundryResourceGovernor()
    for index in range(3):
        eid = f'ephemeral-sponsor-{index}'
        sponsor.register_manifest(eid, team_id=f'team-{index}', sponsor_agent_id='coding.chief', budget=_budget(max_workers=1))
        sponsor.reserve_active(eid)
    sponsor.register_manifest('ephemeral-sponsor-over', team_id='team-3', sponsor_agent_id='coding.chief', budget=_budget(max_workers=1))
    with pytest.raises(PermissionError):
        sponsor.reserve_active('ephemeral-sponsor-over')

    organization = FoundryResourceGovernor()
    for index in range(12):
        eid = f'ephemeral-org-{index}'
        organization.register_manifest(
            eid, team_id=f'team-{index // 3}-{index % 3}', sponsor_agent_id=f'sponsor-{index // 3}',
            budget=_budget(max_workers=1),
        )
        organization.reserve_active(eid)
    organization.register_manifest(
        'ephemeral-org-over', team_id='team-over', sponsor_agent_id='sponsor-over', budget=_budget(max_workers=1),
    )
    with pytest.raises(PermissionError):
        organization.reserve_active('ephemeral-org-over')


def test_retirement_release_is_deterministic_and_state_round_trip_exact():
    governor = FoundryResourceGovernor()
    governor.register_manifest('ephemeral-1', team_id='team-a', sponsor_agent_id='coding.chief', budget=_budget(max_workers=1))
    governor.reserve_active('ephemeral-1')
    governor.consume('ephemeral-1', FoundryResourceKind.EXTERNAL_CORE_CALL, 1, actor_ephemeral_id='ephemeral-1')
    governor.release_active('ephemeral-1')
    state = governor.to_state()
    restored = FoundryResourceGovernor.from_state(state)
    assert restored.to_state() == state
    assert restored.active_ephemeral_ids() == ()
