from cogcoder.organization.coordination import CoordinationBudget, WakeDisposition
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import AgentStatus, EventKind


def _fanout_runtime(agent_ids):
    runtime = OrganizationRuntime.first_generation()
    for agent_id in agent_ids:
        runtime.ledger.subscribe(agent_id, EventKind.PLAN_CHANGE_PROPOSED)
    event = runtime.ledger.append(
        EventKind.PLAN_CHANGE_PROPOSED, source_agent_id='planning.chief',
        payload={'change': 'fanout'}, priority=10,
    )
    return runtime, event


def test_normal_wake_budget_reserves_at_most_eight_and_defers_without_dropping():
    agent_ids = [row.agent_id for row in OrganizationRuntime.first_generation().registry.identities()[:12]]
    runtime, event = _fanout_runtime(agent_ids)
    reservations = runtime.coordination.plan_wakes(event.event_id)
    reserved = [row for row in reservations if row.disposition is WakeDisposition.RESERVED]
    deferred = [row for row in reservations if row.disposition is WakeDisposition.DEFERRED]
    assert len(reserved) <= 8
    assert deferred
    assert len(reserved) + len(deferred) == len(agent_ids)
    runtime.coordination.execute_wakes(event.event_id)
    assert all(runtime.registry.get(row.agent_id).status is AgentStatus.ACTIVE for row in reserved)
    assert all(runtime.registry.get(row.agent_id).status is AgentStatus.SLEEPING for row in deferred)


def test_region_budget_caps_four_even_when_global_capacity_remains():
    coding_ids = [
        'coding.chief', 'coding.core-algorithm.01', 'coding.backend.01',
        'coding.systems.01', 'coding.refactor.01', 'coding.api-interface.01',
    ]
    runtime, event = _fanout_runtime(coding_ids)
    reservations = runtime.coordination.plan_wakes(event.event_id)
    reserved = [row for row in reservations if row.disposition is WakeDisposition.RESERVED]
    assert len(reserved) == 4
    assert all(runtime.registry.get(row.agent_id).region == 'core-coding' for row in reserved)


def test_direct_target_is_prioritized_and_active_agent_does_not_consume_new_slot():
    runtime = OrganizationRuntime.first_generation()
    for agent_id in ('coding.backend.01', 'coding.systems.01', 'data.chief'):
        runtime.ledger.subscribe(agent_id, EventKind.TASK_PROGRESS)
    runtime.scheduler.wake('data.chief', reason='already active')
    event = runtime.ledger.append(
        EventKind.TASK_PROGRESS, source_agent_id='coding.chief', target_agent_id='coding.systems.01',
        region='core-coding', payload={'pct': 25},
    )
    rows = runtime.coordination.plan_wakes(event.event_id)
    reserved = [row for row in rows if row.disposition is WakeDisposition.RESERVED]
    assert reserved[0].agent_id == 'coding.systems.01'
    assert all(row.agent_id != 'data.chief' for row in reserved)


def test_high_severity_mode_can_use_recorded_ceiling_eighteen():
    agent_ids = [row.agent_id for row in OrganizationRuntime.first_generation().registry.identities()[:12]]
    runtime, event = _fanout_runtime(agent_ids)
    runtime.coordination.set_budget(CoordinationBudget(high_severity_max_active_agents=18))
    rows = runtime.coordination.plan_wakes(event.event_id, mode='high_severity')
    assert sum(row.disposition is WakeDisposition.RESERVED for row in rows) == len(agent_ids)
