import pytest

from cogcoder.organization.foundry_resources import FoundryBudget
from cogcoder.organization.runtime import OrganizationRuntime


def _runtime_with_coding_task():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-F14-CODE', title='hard coding task', plan_node_id='P-F14-CODE')
    lease = runtime.coordination.grant_lease('T-F14-CODE', 'coding.backend.01', token=3, stale_after_tokens=20)
    return runtime, lease


def _budget():
    return FoundryBudget(compute_units=40, tool_calls=12, external_core_calls=6, max_workers=2, lifetime_tokens=30)


def test_foundry_has_five_capability_templates_and_ephemeral_is_not_permanent_identity():
    runtime, _ = _runtime_with_coding_task()
    assert len(runtime.registry.identities()) == 67
    assert {row.template_id for row in runtime.foundry.profiles.templates()} == {
        'hypothesis-explorer', 'repository-archaeologist', 'fuzz-counterexample',
        'bug-reproducer', 'migration-compatibility',
    }
    request = runtime.foundry.request_spawn(
        sponsor_agent_id='coding.chief', parent_task_id='T-F14-CODE',
        template_id='bug-reproducer', mission='reproduce the rare retry failure', team_id='team-retry',
        budget=_budget(), requested_tools=('filesystem', 'terminal', 'test-runner'),
        requested_external_cores=('runtime-tracer',), allowed_artifact_kinds=('reproduction', 'evidence'),
        current_token=4,
    )
    approved = runtime.foundry.approve_spawn(request.request_id, actor_agent_id='coding.chief')
    manifest = runtime.foundry.instantiate(approved.request_id, current_token=4)
    assert manifest.sponsor_agent_id == 'coding.chief'
    assert manifest.parent_task_id == 'T-F14-CODE'
    assert manifest.parent_lease_epoch == 1
    assert manifest.memory_namespace.startswith('ephemeral/')
    with pytest.raises(KeyError):
        runtime.registry.get(manifest.ephemeral_id)
    assert len(runtime.registry.identities()) == 67


def test_only_central_or_authorized_own_region_chief_can_spawn():
    runtime, _ = _runtime_with_coding_task()
    with pytest.raises(PermissionError):
        runtime.foundry.request_spawn(
            sponsor_agent_id='coding.backend.01', parent_task_id='T-F14-CODE',
            template_id='bug-reproducer', mission='specialist self spawn', team_id='team-bad',
            budget=_budget(), current_token=4,
        )
    with pytest.raises(PermissionError):
        runtime.foundry.request_spawn(
            sponsor_agent_id='data.chief', parent_task_id='T-F14-CODE',
            template_id='bug-reproducer', mission='wrong region spawn', team_id='team-wrong',
            budget=_budget(), current_token=4,
        )
    request = runtime.foundry.request_spawn(
        sponsor_agent_id='nolane.central', parent_task_id=None,
        template_id='hypothesis-explorer', mission='global diagnostic hypothesis sweep',
        team_id='team-global', budget=_budget(), current_token=10,
    )
    approved = runtime.foundry.approve_spawn(request.request_id, actor_agent_id='nolane.central')
    manifest = runtime.foundry.instantiate(approved.request_id, current_token=10)
    assert manifest.parent_task_id is None
    assert manifest.parent_lease_epoch is None


def test_spawn_scope_cannot_escalate_tools_cores_or_artifact_kinds():
    runtime, _ = _runtime_with_coding_task()
    with pytest.raises(PermissionError):
        runtime.foundry.request_spawn(
            sponsor_agent_id='coding.chief', parent_task_id='T-F14-CODE',
            template_id='bug-reproducer', mission='tool escalation', team_id='team-tool', budget=_budget(),
            requested_tools=('root-shell',), current_token=4,
        )
    with pytest.raises(PermissionError):
        runtime.foundry.request_spawn(
            sponsor_agent_id='coding.chief', parent_task_id='T-F14-CODE',
            template_id='bug-reproducer', mission='core escalation', team_id='team-core', budget=_budget(),
            requested_external_cores=('global-resource-arbiter',), current_token=4,
        )
    with pytest.raises(PermissionError):
        runtime.foundry.request_spawn(
            sponsor_agent_id='coding.chief', parent_task_id='T-F14-CODE',
            template_id='bug-reproducer', mission='artifact escalation', team_id='team-art', budget=_budget(),
            allowed_artifact_kinds=('release-authority',), current_token=4,
        )
