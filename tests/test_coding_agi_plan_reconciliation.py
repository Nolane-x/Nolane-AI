from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.requirements import AcceptanceCriterion, RequirementKind, RequirementNode
from cogcoder.organization.planning import PlanNode
from cogcoder.organization.reconciliation import DriftClass, PlanReconciler


def test_reconciler_detects_orphan_uncovered_and_completion_drift_without_mutation():
    runtime = OrganizationRuntime.first_generation()
    runtime.requirements.apply_revision(
        actor_agent_id='requirements.chief', reason='seed', evidence_refs=('EV-R-1',),
        upserts=(
            RequirementNode('REQ-1', 'Covered', RequirementKind.FUNCTIONAL, 'covered', acceptance_criteria=(AcceptanceCriterion('AC-1','done'),)),
            RequirementNode('REQ-2', 'Uncovered', RequirementKind.FUNCTIONAL, 'uncovered', acceptance_criteria=(AcceptanceCriterion('AC-2','done'),)),
        ),
    )
    runtime.planning.apply_revision(
        actor_agent_id='planning.chief', reason='seed', evidence_refs=('EV-R-2',),
        upsert_nodes=(PlanNode('P-1','Covered plan', requirement_refs=('REQ-1',)),),
    )
    runtime.tasks.add_task('T-ORPHAN', title='orphan', plan_node_id='P-MISSING')
    runtime.tasks.add_task('T-DONE', title='done task', plan_node_id='P-1')
    runtime.tasks.lease('T-DONE', 'coding.backend.01')
    runtime.tasks.complete('T-DONE', 'coding.backend.01', output_artifact_ids=('A-1',))
    before_req = runtime.requirements.to_state()
    before_plan = runtime.planning.to_state()

    findings = PlanReconciler(runtime.requirements, runtime.planning, runtime.tasks).scan()
    kinds = {x.drift_class for x in findings}
    assert DriftClass.ORPHAN_TASK in kinds
    assert DriftClass.UNCOVERED_REQUIREMENT in kinds
    assert DriftClass.COMPLETION_DRIFT in kinds
    assert runtime.requirements.to_state() == before_req
    assert runtime.planning.to_state() == before_plan
