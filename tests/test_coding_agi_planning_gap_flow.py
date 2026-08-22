from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.requirements import AcceptanceCriterion, RequirementKind, RequirementNode
from cogcoder.organization.planning import PlanNode
from cogcoder.organization.types import EventKind


def test_coder_plan_gap_is_applied_by_planning_chief_and_traced_to_task():
    runtime = OrganizationRuntime.first_generation()
    runtime.requirements.apply_revision(
        actor_agent_id='requirements.chief', reason='seed', evidence_refs=('EV-G-1',),
        upserts=(RequirementNode(
            requirement_id='REQ-1', title='Durable store', kind=RequirementKind.FUNCTIONAL,
            description='persist state', acceptance_criteria=(AcceptanceCriterion('AC-1', 'survives restart'),),
        ),),
    )
    runtime.planning.apply_revision(
        actor_agent_id='planning.chief', reason='seed plan', evidence_refs=('EV-G-2',),
        upsert_nodes=(PlanNode('P-1', 'Implement store', requirement_refs=('REQ-1',)),),
    )
    runtime.tasks.add_task('T-1', title='Implement store', plan_node_id='P-1')
    runtime.tasks.lease('T-1', 'coding.backend.01')

    gap = runtime.report_plan_gap(
        source_agent_id='coding.backend.01', task_id='T-1',
        reason='migration and rollback are missing',
        suggested_nodes=('P-MIGRATE', 'P-ROLLBACK'), evidence_ids=('EV-G-3',),
    )
    before = runtime.planning.graph.version
    result = runtime.planning.apply_gap(
        proposal_event_id=gap.event_id, actor_agent_id='planning.chief',
        added_nodes=(
            PlanNode('P-MIGRATE', 'Add migration', dependencies=('P-1',), requirement_refs=('REQ-1',)),
            PlanNode('P-ROLLBACK', 'Add rollback', dependencies=('P-MIGRATE',), requirement_refs=('REQ-1',)),
        ),
        evidence_refs=('EV-G-4',), affected_tasks=('T-1',),
    )
    assert result.revision.version == before + 1
    assert result.event.kind is EventKind.PLAN_AMENDED
    assert result.event.payload['affected_tasks'] == ['T-1']
    assert runtime.planning.plan_node_for_task('T-1') == 'P-1'
    delta = runtime.planning.plan_delta(before)
    assert set(delta.added_nodes) == {'P-MIGRATE', 'P-ROLLBACK'}
    assert delta.affected_tasks == ('T-1',)
