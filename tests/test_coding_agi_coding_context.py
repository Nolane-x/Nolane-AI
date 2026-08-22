from cogcoder.organization.coding_profiles import CodingDomain, CodingWorkRequest
from cogcoder.organization.runtime import OrganizationRuntime


def test_checkpointed_coder_wakes_with_authoritative_coding_state_reference():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-CONTEXT', title='Backend context task', plan_node_id='P-CONTEXT')
    runtime.tasks.lease('T-CONTEXT', 'coding.backend.01')
    runtime.checkpoint_agent('coding.backend.01')

    runtime.coding.request_work(CodingWorkRequest(
        work_id='W-CONTEXT', task_id='T-CONTEXT', plan_node_id='P-CONTEXT',
        requirement_refs=(), architecture_version=runtime.architecture.graph.version,
        plan_version=runtime.planning.graph.version,
        requested_domains=(CodingDomain.BACKEND,), scope_hints=('service',),
        acceptance_refs=('AC-CONTEXT',), priority=60,
        requester_agent_id='coding.chief', evidence_refs=('EV-CONTEXT-WORK',),
    ))
    runtime.coding.claim_sources(
        agent_id='coding.backend.01', task_id='T-CONTEXT',
        file_paths=('src/context_service.py',),
    )

    capsule = runtime.wake_agent('coding.backend.01', reason='coding work changed')
    assert ('coding-state', runtime.coding.digest) in capsule.authoritative_artifacts
    assert any(event.source_agent_id in {'coding.chief', 'coding.backend.01'} for event in capsule.event_delta)
