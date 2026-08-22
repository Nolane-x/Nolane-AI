import pytest

from cogcoder.organization.foundry_lifecycle import FoundryStatus
from cogcoder.organization.foundry_memory import EphemeralScratchVault, ScratchDisposition
from cogcoder.organization.foundry_resources import FoundryBudget
from cogcoder.organization.runtime import OrganizationRuntime


def _active_foundry_worker():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-F14-LIFE', title='lifecycle task', plan_node_id='P-F14-LIFE')
    runtime.coordination.grant_lease('T-F14-LIFE', 'debug.reproducer.01', token=1, stale_after_tokens=20)
    request = runtime.foundry.request_spawn(
        sponsor_agent_id='debug.chief', parent_task_id='T-F14-LIFE', template_id='bug-reproducer',
        mission='isolate lifecycle failure', team_id='team-life',
        budget=FoundryBudget(compute_units=20, tool_calls=8, external_core_calls=4, max_workers=2, lifetime_tokens=20),
        current_token=2,
    )
    runtime.foundry.approve_spawn(request.request_id, actor_agent_id='debug.chief')
    manifest = runtime.foundry.instantiate(request.request_id, current_token=2)
    runtime.foundry.activate(manifest.ephemeral_id, actor_agent_id='debug.chief')
    return runtime, manifest


def test_success_lifecycle_is_forward_only_and_retired_worker_cannot_reactivate():
    runtime, manifest = _active_foundry_worker()
    assert runtime.foundry.status(manifest.ephemeral_id) is FoundryStatus.ACTIVE
    runtime.foundry.begin_verification(manifest.ephemeral_id, actor_agent_id='debug.chief')
    assert runtime.foundry.status(manifest.ephemeral_id) is FoundryStatus.VERIFYING
    runtime.foundry.mark_handoff(manifest.ephemeral_id, actor_agent_id='debug.chief')
    retired = runtime.foundry.retire(
        manifest.ephemeral_id, actor_agent_id='debug.chief', scratch_policy=ScratchDisposition.DESTROY,
    )
    assert retired.to_status is FoundryStatus.RETIRED
    with pytest.raises(PermissionError):
        runtime.foundry.activate(manifest.ephemeral_id, actor_agent_id='debug.chief')


def test_unauthorized_actor_cannot_transition_or_hide_failure():
    runtime, manifest = _active_foundry_worker()
    with pytest.raises(PermissionError):
        runtime.foundry.quarantine(manifest.ephemeral_id, actor_agent_id='coding.backend.01', reason='hide worker')
    row = runtime.foundry.quarantine(
        manifest.ephemeral_id, actor_agent_id='debug.chief', reason='invalid reproduction evidence',
    )
    assert row.to_status is FoundryStatus.QUARANTINED
    with pytest.raises(PermissionError):
        runtime.foundry.activate(manifest.ephemeral_id, actor_agent_id='nolane.central')


def test_scratch_vault_is_worker_private_and_destroy_removes_content_from_state():
    vault = EphemeralScratchVault()
    vault.register('ephemeral-a', team_id='team-a')
    vault.register('ephemeral-b', team_id='team-a')
    entry = vault.write('ephemeral-a', 'SECRET-FAILED-HYPOTHESIS', actor_ephemeral_id='ephemeral-a')
    assert vault.read('ephemeral-a', actor_ephemeral_id='ephemeral-a') == (entry,)
    with pytest.raises(PermissionError):
        vault.read('ephemeral-a', actor_ephemeral_id='ephemeral-b')
    with pytest.raises(PermissionError):
        vault.read('ephemeral-a', actor_ephemeral_id='debug.chief')
    tombstones = vault.retire('ephemeral-a', ScratchDisposition.DESTROY)
    assert tombstones and tombstones[0].content_digest == entry.content_digest
    state = vault.to_state()
    assert 'SECRET-FAILED-HYPOTHESIS' not in repr(state)
    restored = EphemeralScratchVault.from_state(state)
    assert restored.to_state() == state
    assert restored.destroyed_tombstones('ephemeral-a') == tombstones


def test_foundry_scratch_never_writes_permanent_memory_and_archive_is_quarantined():
    runtime, manifest = _active_foundry_worker()
    before = runtime.memory.to_state()
    runtime.foundry.write_scratch(
        manifest.ephemeral_id, 'temporary counterexample notes', actor_ephemeral_id=manifest.ephemeral_id,
    )
    runtime.foundry.retire(
        manifest.ephemeral_id, actor_agent_id='debug.chief', scratch_policy=ScratchDisposition.ARCHIVE_QUARANTINE,
    )
    assert runtime.memory.to_state() == before
    archive = runtime.foundry.scratch.archived_entries(manifest.ephemeral_id)
    assert archive and all(row.quarantined for row in archive)
