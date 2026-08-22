import copy
import pytest

from cogcoder.organization.foundry_memory import ScratchDisposition
from cogcoder.organization.foundry_resources import FoundryBudget, FoundryResourceKind
from cogcoder.organization.runtime import OrganizationRuntime


def _rich_runtime():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-F14-SNAP', title='foundry snapshot task', plan_node_id='P-F14-SNAP')
    runtime.coordination.grant_lease('T-F14-SNAP', 'research.repo-archaeology.01', token=1, stale_after_tokens=50)
    request = runtime.foundry.request_spawn(
        sponsor_agent_id='research.chief', parent_task_id='T-F14-SNAP',
        template_id='repository-archaeologist', mission='trace historical API contract', team_id='team-snap',
        budget=FoundryBudget(compute_units=25, tool_calls=9, external_core_calls=4, max_workers=2, lifetime_tokens=40),
        requested_tools=('filesystem', 'git', 'code-search'),
        requested_external_cores=('github-research',), allowed_artifact_kinds=('research-note', 'evidence'),
        current_token=2,
    )
    runtime.foundry.approve_spawn(request.request_id, actor_agent_id='research.chief')
    manifest = runtime.foundry.instantiate(request.request_id, current_token=2)
    runtime.foundry.activate(manifest.ephemeral_id, actor_agent_id='research.chief')
    runtime.foundry.consume(
        manifest.ephemeral_id, FoundryResourceKind.COMPUTE, 5, actor_ephemeral_id=manifest.ephemeral_id,
    )
    runtime.foundry.write_scratch(
        manifest.ephemeral_id, 'TEMP-SNAPSHOT-SECRET', actor_ephemeral_id=manifest.ephemeral_id,
    )
    runtime.foundry.emit_output(
        manifest.ephemeral_id, kind='research-note', content='API changed after commit family X',
        evidence_refs=('EV-HISTORY',),
    )
    return runtime, manifest


def test_zero_ephemeral_runtime_is_valid_and_old_part13_snapshot_restores_empty_foundry():
    runtime = OrganizationRuntime.first_generation()
    assert runtime.foundry.manifests() == ()
    assert runtime.foundry.spawn_requests() == ()
    state = runtime.to_state()
    assert 'foundry' in state
    legacy = copy.deepcopy(state)
    legacy.pop('foundry')
    restored = OrganizationRuntime.from_state(legacy)
    assert restored.foundry.manifests() == ()
    assert restored.foundry.spawn_requests() == ()
    assert restored.foundry.outputs() == ()
    for key, value in legacy.items():
        assert restored.to_state()[key] == value


def test_rich_foundry_runtime_snapshot_round_trip_is_exact():
    runtime, _ = _rich_runtime()
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(state)
    assert restored.to_state() == state


def test_destroyed_scratch_plaintext_never_reappears_after_restore():
    runtime, manifest = _rich_runtime()
    runtime.foundry.retire(
        manifest.ephemeral_id, actor_agent_id='research.chief', scratch_policy=ScratchDisposition.DESTROY,
    )
    state = runtime.to_state()
    assert 'TEMP-SNAPSHOT-SECRET' not in repr(state)
    restored = OrganizationRuntime.from_state(state)
    assert 'TEMP-SNAPSHOT-SECRET' not in repr(restored.to_state())
    assert restored.foundry.scratch.destroyed_tombstones(manifest.ephemeral_id)


def test_corrupt_manifest_digest_or_budget_fails_closed_on_restore():
    runtime, _ = _rich_runtime()
    state = runtime.to_state()
    bad_manifest = copy.deepcopy(state)
    bad_manifest['foundry']['profiles']['manifests'][0]['digest'] = '0' * 64
    with pytest.raises(ValueError):
        OrganizationRuntime.from_state(bad_manifest)

    bad_budget = copy.deepcopy(state)
    key = next(iter(bad_budget['foundry']['resources']['registrations']))
    bad_budget['foundry']['resources']['registrations'][key]['budget']['compute_units'] = -1
    with pytest.raises(ValueError):
        OrganizationRuntime.from_state(bad_budget)
