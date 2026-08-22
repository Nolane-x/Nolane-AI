from cogcoder.organization.coding_profiles import CodingDomain, CodingWorkRequest
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import SkillScope


def test_coding_chief_personally_owns_and_completes_implementation_with_patch_provenance():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-CHIEF', title='Repair cross-system adapter', plan_node_id='P-CHIEF')
    runtime.tasks.lease('T-CHIEF', 'coding.chief')

    assignment = runtime.coding.request_work(CodingWorkRequest(
        work_id='W-CHIEF', task_id='T-CHIEF', plan_node_id='P-CHIEF',
        requirement_refs=(), architecture_version=runtime.architecture.graph.version,
        plan_version=runtime.planning.graph.version,
        requested_domains=(CodingDomain.CROSS_SYSTEM,),
        scope_hints=('cross-system', 'integration'), acceptance_refs=('AC-CHIEF',),
        priority=90, requester_agent_id='coding.chief', evidence_refs=('EV-CHIEF-WORK',),
    ))
    assert assignment.selected_agent_id == 'coding.chief'

    runtime.coding.claim_sources(
        agent_id='coding.chief', task_id='T-CHIEF',
        file_paths=('src/adapters/bridge.py',), symbol_ids=('BridgeAdapter.translate',),
    )
    patch = runtime.coding.submit_patch(
        producer_agent_id='coding.chief', task_id='T-CHIEF', work_id='W-CHIEF',
        touched_files=('src/adapters/bridge.py',), touched_symbols=('BridgeAdapter.translate',),
        patch_artifact_id='artifact-chief-patch',
        compile_evidence_refs=('EV-CHIEF-COMPILE',), test_evidence_refs=('EV-CHIEF-TEST',),
    )

    receipt = runtime.chief_direct_work(
        'coding.chief', 'T-CHIEF', output_artifact_ids=(patch.patch_artifact_id,),
    )
    assert receipt['chief_agent_id'] == 'coding.chief'
    assert runtime.tasks.get('T-CHIEF').completed_by == 'coding.chief'
    assert runtime.tasks.get('T-CHIEF').output_artifact_ids == ('artifact-chief-patch',)

    skill = runtime.coding.propose_personal_skill_from_patch(
        patch.patch_id,
        name='cross-system adapter repair',
        body='preserve interface semantics while translating adapter state',
    )
    assert skill.owner_agent_id == 'coding.chief'
    assert skill.scope is SkillScope.CANDIDATE
