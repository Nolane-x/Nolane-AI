from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.snapshot import OrganizationSnapshot
from cogcoder.organization.requirements import AcceptanceCriterion, RequirementKind, RequirementNode
from cogcoder.organization.planning import PlanNode
from cogcoder.organization.types import EventKind


def test_requirements_and_plan_restore_exactly_from_snapshot():
    runtime = OrganizationRuntime.first_generation()
    runtime.requirements.apply_revision(
        actor_agent_id='requirements.chief', reason='seed', evidence_refs=('EV-S-1',),
        upserts=(RequirementNode('REQ-1','Durable jobs',RequirementKind.FUNCTIONAL,'persist',acceptance_criteria=(AcceptanceCriterion('AC-1','restart safe'),)),),
    )
    runtime.planning.apply_revision(
        actor_agent_id='planning.chief', reason='seed plan', evidence_refs=('EV-S-2',),
        upsert_nodes=(PlanNode('P-1','Implement durability',requirement_refs=('REQ-1',)),),
    )
    snap = OrganizationSnapshot.capture(runtime)
    restored = OrganizationSnapshot.from_json(snap.to_json()).restore()
    assert restored.requirements.to_state() == runtime.requirements.to_state()
    assert restored.planning.to_state() == runtime.planning.to_state()
    assert restored.requirements.graph.digest == runtime.requirements.graph.digest
    assert restored.planning.graph.digest == runtime.planning.graph.digest


def test_checkpointed_coder_wakes_with_authoritative_plan_delta_not_full_history():
    runtime = OrganizationRuntime.first_generation()
    runtime.requirements.apply_revision(
        actor_agent_id='requirements.chief', reason='seed', evidence_refs=('EV-C-1',),
        upserts=(RequirementNode('REQ-1','Store',RequirementKind.FUNCTIONAL,'persist',acceptance_criteria=(AcceptanceCriterion('AC-1','durable'),)),),
    )
    runtime.planning.apply_revision(
        actor_agent_id='planning.chief', reason='seed plan', evidence_refs=('EV-C-2',),
        upsert_nodes=(PlanNode('P-1','Store',requirement_refs=('REQ-1',)),),
    )
    runtime.tasks.add_task('T-1', title='Store', plan_node_id='P-1')
    runtime.tasks.lease('T-1', 'coding.backend.01')
    checkpoint = runtime.checkpoint_agent('coding.backend.01')

    gap = runtime.report_plan_gap(
        source_agent_id='coding.backend.01', task_id='T-1', reason='rollback missing',
        suggested_nodes=('P-ROLLBACK',), evidence_ids=('EV-C-3',),
    )
    runtime.planning.apply_gap(
        proposal_event_id=gap.event_id, actor_agent_id='planning.chief',
        added_nodes=(PlanNode('P-ROLLBACK','Rollback',dependencies=('P-1',),requirement_refs=('REQ-1',)),),
        evidence_refs=('EV-C-4',), affected_tasks=('T-1',),
    )
    capsule = runtime.wake_agent('coding.backend.01', reason='plan changed')
    assert capsule.since_event_id == checkpoint
    assert capsule.plan_version == runtime.planning.graph.version
    assert ('requirements', runtime.requirements.graph.version) in capsule.authoritative_artifacts
    assert ('master-plan', runtime.planning.graph.version) in capsule.authoritative_artifacts
    assert any(e.kind is EventKind.PLAN_AMENDED for e in capsule.event_delta)
