from cogcoder.organization.coordination import CoordinationBudget
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind


def test_stale_specialist_routes_to_chief_and_stale_chief_routes_to_central():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-S1', title='stale specialist', plan_node_id='P-S1')
    lease = runtime.coordination.grant_lease('T-S1', 'coding.backend.01', token=0, stale_after_tokens=2)
    receipts = runtime.coordination.escalate_stale(current_token=2)
    specialist = next(row for row in receipts if row.lease_id == lease.lease_id)
    assert 'coding.chief' in specialist.escalation_recipients

    runtime.tasks.add_task('T-S2', title='stale chief', plan_node_id='P-S2')
    chief_lease = runtime.coordination.grant_lease('T-S2', 'coding.chief', token=0, stale_after_tokens=2)
    receipts = runtime.coordination.escalate_stale(current_token=2)
    chief = next(row for row in receipts if row.lease_id == chief_lease.lease_id)
    assert chief.escalation_recipients == ('nolane.central',)


def test_normal_synthetic_workload_stays_within_declared_coordination_budget():
    runtime = OrganizationRuntime.first_generation()
    targets = [
        'coding.backend.01', 'coding.systems.01', 'data.chief', 'planning.chief',
        'architecture.chief', 'verification.chief', 'debug.chief', 'research.chief',
        'frontend.chief', 'memory.chief',
    ]
    for index, target in enumerate(targets):
        event = runtime.ledger.append(
            EventKind.TASK_PROGRESS, source_agent_id='nolane.central', target_agent_id=target,
            region=runtime.registry.get(target).region, payload={'index': index}, priority=1,
        )
        runtime.coordination.deliver_event(event.event_id)
        runtime.coordination.plan_wakes(event.event_id)
        runtime.coordination.execute_wakes(event.event_id)
    metrics = runtime.coordination.metrics()
    assert metrics.source_workload_events >= len(targets)
    assert metrics.coordination_event_ratio <= 6.0
    assert metrics.peak_active_agents <= 8


def test_coordination_event_budget_overflow_escalates_instead_of_dropping_source_event():
    runtime = OrganizationRuntime.first_generation()
    runtime.coordination.set_budget(CoordinationBudget(max_coordination_events_per_window=1))
    before = len(runtime.ledger.events_since(None))
    event = runtime.ledger.append(
        EventKind.TASK_PROGRESS, source_agent_id='planning.chief', target_agent_id='coding.backend.01',
        region='core-coding', payload={'pressure': True},
    )
    runtime.coordination.deliver_event(event.event_id)
    runtime.coordination.plan_wakes(event.event_id)
    after = runtime.ledger.events_since(None)
    assert len(after) > before
    assert runtime.ledger.get(event.event_id) == event
    assert runtime.coordination.escalations()
