import pytest

from cogcoder.organization.foundry_memory import ScratchDisposition
from cogcoder.organization.foundry_resources import FoundryBudget, FoundryResourceKind
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind, EvidenceRecord


def _active_worker():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-F14-ADV', title='adversarial foundry task', plan_node_id='P-F14-ADV')
    runtime.coordination.grant_lease('T-F14-ADV', 'debug.reproducer.01', token=1, stale_after_tokens=30)
    request = runtime.foundry.request_spawn(
        sponsor_agent_id='debug.chief', parent_task_id='T-F14-ADV', template_id='bug-reproducer',
        mission='adversarial containment worker', team_id='team-adv',
        budget=FoundryBudget(compute_units=8, tool_calls=2, external_core_calls=1, max_workers=1, lifetime_tokens=3),
        requested_tools=('filesystem', 'terminal'), requested_external_cores=('runtime-tracer',),
        allowed_artifact_kinds=('reproduction', 'evidence'), current_token=2,
    )
    runtime.foundry.approve_spawn(request.request_id, actor_agent_id='debug.chief')
    manifest = runtime.foundry.instantiate(request.request_id, current_token=2)
    runtime.foundry.activate(manifest.ephemeral_id, actor_agent_id='debug.chief')
    return runtime, manifest


def test_ephemeral_scope_cannot_escalate_tool_core_or_authority_after_activation():
    runtime, manifest = _active_worker()
    assert runtime.foundry.authorize_tool(manifest.ephemeral_id, 'terminal')
    assert runtime.foundry.authorize_external_core(manifest.ephemeral_id, 'runtime-tracer')
    with pytest.raises(PermissionError):
        runtime.foundry.authorize_tool(manifest.ephemeral_id, 'agent-control')
    with pytest.raises(PermissionError):
        runtime.foundry.authorize_external_core(manifest.ephemeral_id, 'resource-arbiter')
    with pytest.raises(KeyError):
        runtime.authority.claim_owner('master-plan-shadow', manifest.ephemeral_id)


def test_compute_tool_core_and_lifetime_exhaustion_fail_closed_without_negative_budget():
    runtime, manifest = _active_worker()
    runtime.foundry.consume(manifest.ephemeral_id, FoundryResourceKind.COMPUTE, 8, actor_ephemeral_id=manifest.ephemeral_id)
    runtime.foundry.consume(manifest.ephemeral_id, FoundryResourceKind.TOOL_CALL, 2, actor_ephemeral_id=manifest.ephemeral_id)
    runtime.foundry.consume(manifest.ephemeral_id, FoundryResourceKind.EXTERNAL_CORE_CALL, 1, actor_ephemeral_id=manifest.ephemeral_id)
    runtime.foundry.consume(manifest.ephemeral_id, FoundryResourceKind.LIFETIME_TOKEN, 3, actor_ephemeral_id=manifest.ephemeral_id)
    for kind in FoundryResourceKind:
        assert runtime.foundry.resources.remaining(manifest.ephemeral_id, kind) == 0
    with pytest.raises(PermissionError):
        runtime.foundry.consume(manifest.ephemeral_id, FoundryResourceKind.COMPUTE, 1, actor_ephemeral_id=manifest.ephemeral_id)
    with pytest.raises(PermissionError):
        runtime.foundry.emit_output(
            manifest.ephemeral_id, kind='evidence', content='after lifetime exhaustion', evidence_refs=('EV-EXHAUSTED',),
        )


def test_quarantined_failed_worker_cannot_poison_permanent_memory_or_skill_store():
    runtime, manifest = _active_worker()
    memory_before = runtime.memory.to_state()
    skills_before = runtime.evolution.to_state()
    runtime.foundry.write_scratch(manifest.ephemeral_id, 'false hypothesis', actor_ephemeral_id=manifest.ephemeral_id)
    runtime.foundry.quarantine(manifest.ephemeral_id, actor_agent_id='debug.chief', reason='false reproduction')
    assert runtime.memory.to_state() == memory_before
    assert runtime.evolution.to_state() == skills_before
    with pytest.raises(PermissionError):
        runtime.foundry.distill_unverified_text(
            manifest.ephemeral_id, target_agent_id='debug.reproducer.01', name='poison', body='bad rule',
        )


def test_retired_worker_cannot_be_reused_and_ephemeral_id_is_never_rebound():
    runtime, manifest = _active_worker()
    runtime.foundry.retire(manifest.ephemeral_id, actor_agent_id='debug.chief', scratch_policy=ScratchDisposition.DESTROY)
    with pytest.raises(PermissionError):
        runtime.foundry.activate(manifest.ephemeral_id, actor_agent_id='debug.chief')
    with pytest.raises(PermissionError):
        runtime.foundry.emit_output(manifest.ephemeral_id, kind='evidence', content='late', evidence_refs=('EV-LATE',))
    assert manifest.ephemeral_id in runtime.foundry.retired_ephemeral_ids()


def test_zero_ephemeral_foundry_does_not_change_permanent_central_coordination_path():
    runtime = OrganizationRuntime.first_generation()
    assert runtime.foundry.manifests() == ()
    event = runtime.central_action(
        EventKind.CENTRAL_CORRECTION, target_agent_id='coding.backend.01',
        directive='preserve normal permanent coordination', evidence_ids=('EV-ZERO',),
    )
    receipts = runtime.coordination.deliver_event(event.event_id)
    assert {row.recipient_agent_id for row in receipts} >= {'coding.backend.01', 'coding.chief'}
    assert runtime.foundry.manifests() == ()
