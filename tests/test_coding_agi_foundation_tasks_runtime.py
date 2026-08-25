import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind


def test_task_lease_is_single_owner_and_chief_can_work_directly():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-900', title='Repair cross-module interface', plan_node_id='P-90')
    runtime.tasks.lease('T-900', 'coding.chief')

    with pytest.raises(ValueError, match='already leased'):
        runtime.tasks.lease('T-900', 'coding.backend.01')

    receipt = runtime.chief_direct_work('coding.chief', 'T-900', output_artifact_ids=('PATCH-1',))
    assert receipt['chief_agent_id'] == 'coding.chief'
    assert runtime.tasks.get('T-900').completed_by == 'coding.chief'
    assert any(event.kind is EventKind.CHIEF_DIRECT_WORK for event in runtime.ledger.events_since(None))


def test_central_can_correct_specialist_directly_and_chief_observes_same_event():
    runtime = OrganizationRuntime.first_generation()
    event = runtime.central_intervene(
        target_agent_id='debug.runtime-trace.01',
        directive='Re-evaluate H17 with mutable state semantics',
        evidence_ids=('TRACE-9',),
    )
    assert event.source_agent_id == 'nolane.central'
    assert event.target_agent_id == 'debug.runtime-trace.01'
    assert event in runtime.ledger.deliverable_for('debug.runtime-trace.01')
    assert event in runtime.ledger.deliverable_for('debug.chief')


def test_coder_plan_gap_requires_planning_authority_then_returns_context_delta():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-184', title='Add durable job store', plan_node_id='P-41')
    runtime.tasks.lease('T-184', 'coding.backend.01')

    proposal = runtime.report_plan_gap(
        source_agent_id='coding.backend.01',
        task_id='T-184',
        reason='Persistence requires a schema migration and rollback test',
        suggested_nodes=('P-41-migration', 'P-41-rollback'),
        evidence_ids=('CODE-88',),
    )
    assert proposal.kind is EventKind.PLAN_GAP_DETECTED
    # Wave 5N established MasterPlanGraph as the only mutable revision clock.
    # A gap proposal is evidence, not a plan mutation.
    assert runtime.tasks.plan_version == 0

    with pytest.raises(PermissionError):
        runtime.tasks.apply_plan_amendment('coding.backend.01', proposal.event_id, added_nodes=('P-41-migration',))
    assert runtime.tasks.plan_version == 0

    amendment = runtime.tasks.apply_plan_amendment(
        'planning.chief',
        proposal.event_id,
        added_nodes=('P-41-migration', 'P-41-rollback'),
    )
    assert amendment.kind is EventKind.PLAN_AMENDED
    assert runtime.tasks.plan_version == 1

    capsule = runtime.context.compile('coding.backend.01', task_id='T-184', since_event_id=proposal.event_id)
    assert amendment in capsule.event_delta
