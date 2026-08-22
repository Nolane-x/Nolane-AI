from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.snapshot import OrganizationSnapshot
from cogcoder.organization.types import EventKind, MemoryScope


def test_snapshot_is_canonical_and_restart_preserves_authoritative_state():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-7', title='Trace persistent failure', plan_node_id='P-7')
    runtime.tasks.lease('T-7', 'debug.runtime-trace.01')
    runtime.memory.write(MemoryScope.PERSONAL, 'known trace signature', owner_agent_id='debug.runtime-trace.01')
    runtime.ledger.append(
        EventKind.TASK_STARTED,
        source_agent_id='debug.runtime-trace.01',
        target_agent_id='debug.runtime-trace.01',
        region='debugging-failure',
        payload={'task_id': 'T-7'},
    )
    runtime.registry.accept_neural_version('debug.runtime-trace.01', 'runtime-trace-delta-0.2')

    first = OrganizationSnapshot.capture(runtime)
    second = OrganizationSnapshot.capture(runtime)
    assert first.to_json() == second.to_json()
    assert first.digest == second.digest

    restored = OrganizationSnapshot.from_json(first.to_json()).restore()
    assert restored.registry.get('debug.runtime-trace.01').neural_version == 'runtime-trace-delta-0.2'
    assert restored.tasks.get('T-7').leased_to == 'debug.runtime-trace.01'
    assert [row.text for row in restored.memory.read_personal('debug.runtime-trace.01')] == ['known trace signature']
    assert restored.ledger.events_since(None)[0].kind is EventKind.TASK_STARTED


def test_snapshot_digest_changes_when_authoritative_state_changes():
    runtime = OrganizationRuntime.first_generation()
    before = OrganizationSnapshot.capture(runtime)
    runtime.tasks.add_task('T-99', title='New authoritative task', plan_node_id='P-99')
    after = OrganizationSnapshot.capture(runtime)
    assert before.digest != after.digest
