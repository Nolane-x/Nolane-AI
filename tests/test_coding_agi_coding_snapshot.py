from cogcoder.organization.coding_profiles import CodingDomain, CodingWorkRequest
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.snapshot import OrganizationSnapshot


def test_coding_state_round_trips_exactly_through_organization_snapshot():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-SNAPSHOT', title='Backend change', plan_node_id='P-SNAPSHOT')
    runtime.tasks.lease('T-SNAPSHOT', 'coding.backend.01')

    runtime.coding.request_work(CodingWorkRequest(
        work_id='W-SNAPSHOT', task_id='T-SNAPSHOT', plan_node_id='P-SNAPSHOT',
        requirement_refs=(), architecture_version=runtime.architecture.graph.version,
        plan_version=runtime.planning.graph.version,
        requested_domains=(CodingDomain.BACKEND,), scope_hints=('service',),
        acceptance_refs=('AC-SNAPSHOT',), priority=40,
        requester_agent_id='coding.chief', evidence_refs=('EV-SNAPSHOT-WORK',),
    ))
    runtime.coding.claim_sources(
        agent_id='coding.backend.01', task_id='T-SNAPSHOT',
        file_paths=('src/service.py',), symbol_ids=('Service.run',),
    )
    patch = runtime.coding.submit_patch(
        producer_agent_id='coding.backend.01', task_id='T-SNAPSHOT', work_id='W-SNAPSHOT',
        touched_files=('src/service.py',), touched_symbols=('Service.run',),
        patch_artifact_id='artifact-snapshot-patch',
        compile_evidence_refs=('EV-SNAPSHOT-COMPILE',),
        test_evidence_refs=('EV-SNAPSHOT-TEST',),
    )
    runtime.coding.patches.record_tool_invocation(
        agent_id='coding.backend.01', task_id='T-SNAPSHOT', tool_id='compiler',
        input_artifact_refs=(patch.patch_artifact_id,),
        output_artifact_refs=('artifact-snapshot-build',),
        success=True, evidence_refs=('EV-SNAPSHOT-TOOL',),
    )

    before = runtime.coding.to_state()
    snapshot = OrganizationSnapshot.capture(runtime)
    restored = snapshot.restore()

    assert restored.coding.to_state() == before
    assert OrganizationSnapshot.capture(restored).digest == snapshot.digest
