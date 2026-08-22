from cogcoder.organization.runtime import OrganizationRuntime


def test_requirements_and_planning_chiefs_are_direct_workers_not_dispatchers():
    runtime = OrganizationRuntime.first_generation()

    runtime.tasks.add_task('T-RQ', title='Resolve acceptance ambiguity', plan_node_id='P-RQ')
    runtime.tasks.lease('T-RQ', 'requirements.chief')
    rq_artifact = runtime.artifacts.put(
        kind='requirements-analysis', producer_agent_id='requirements.chief',
        content='resolved latency acceptance criteria', evidence_refs=('EV-DW-1',),
    )
    rq_receipt = runtime.chief_direct_work(
        'requirements.chief', 'T-RQ', output_artifact_ids=(rq_artifact.artifact_id,),
    )
    assert rq_receipt['chief_agent_id'] == 'requirements.chief'

    runtime.tasks.add_task('T-PLAN', title='Repair dependency plan', plan_node_id='P-PLAN')
    runtime.tasks.lease('T-PLAN', 'planning.chief')
    plan_artifact = runtime.artifacts.put(
        kind='plan-analysis', producer_agent_id='planning.chief',
        content='reconciled dependency DAG', evidence_refs=('EV-DW-2',),
    )
    plan_receipt = runtime.chief_direct_work(
        'planning.chief', 'T-PLAN', output_artifact_ids=(plan_artifact.artifact_id,),
    )
    assert plan_receipt['chief_agent_id'] == 'planning.chief'
    assert runtime.tasks.get('T-RQ').completed_by == 'requirements.chief'
    assert runtime.tasks.get('T-PLAN').completed_by == 'planning.chief'
