from cogcoder.organization.context_intelligence import ContextBudget, ContextDeltaKind
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind, MemoryScope


def test_long_sleep_resume_uses_checkpoint_delta_not_full_event_history():
    runtime = OrganizationRuntime.first_generation()
    for index in range(40):
        runtime.ledger.append(
            EventKind.EVIDENCE_ADDED, source_agent_id='research.chief', region='research-external',
            payload={'historical': index}, evidence_refs=(f'EV-H-{index}',),
        )
    runtime.tasks.add_task('T-RESUME', title='Resume bounded mission', plan_node_id='P-RESUME')
    runtime.tasks.lease('T-RESUME', 'coding.backend.01')
    runtime.checkpoint_agent('coding.backend.01')
    checkpoint = runtime.memory_context.capture_continuity('coding.backend.01')

    for index in range(30):
        runtime.ledger.append(
            EventKind.EVIDENCE_ADDED, source_agent_id='research.chief', region='research-external',
            payload={'irrelevant_after_checkpoint': index}, evidence_refs=(f'EV-I-{index}',),
        )
    runtime.memory.write(
        MemoryScope.PERSONAL, 'current task requires idempotent retry', owner_agent_id='coding.backend.01',
        task_id=None, tags=('retry',), evidence_ids=('EV-RETRY',), confidence=0.9,
    )
    runtime.central_intervene(
        target_agent_id='coding.backend.01', directive='retain idempotency guarantee', evidence_ids=('EV-DIRECT',),
    )

    result = runtime.memory_context.compile_context(
        'coding.backend.01', continuity_checkpoint_id=checkpoint.checkpoint_id,
        budget=ContextBudget(max_memories=16, max_events=8, max_estimated_units=4096),
    )
    total_events = len(runtime.ledger.to_state()['events'])
    assert result.receipt.replayed_full_history is False
    assert result.receipt.event_candidate_count < total_events
    assert len(result.capsule.event_delta) <= 8
    assert any(item.kind is ContextDeltaKind.CENTRAL_INTERVENTION for item in result.delta.items)


def test_task_reassignment_while_sleeping_is_detected_from_continuity_frontier():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-OLD', title='Old task', plan_node_id='P-OLD')
    runtime.tasks.lease('T-OLD', 'coding.backend.01')
    runtime.checkpoint_agent('coding.backend.01')
    checkpoint = runtime.memory_context.capture_continuity('coding.backend.01')

    runtime.tasks.abort('T-OLD', 'nolane.central', reason='mission changed')
    runtime.tasks.add_task('T-NEW', title='New task', plan_node_id='P-NEW')
    runtime.tasks.lease('T-NEW', 'coding.backend.01')

    result = runtime.memory_context.compile_context(
        'coding.backend.01', continuity_checkpoint_id=checkpoint.checkpoint_id,
        budget=ContextBudget(max_memories=16, max_events=16, max_estimated_units=4096),
    )
    assert result.capsule.task_id == 'T-NEW'
    assert any(item.kind is ContextDeltaKind.TASK_CHANGED for item in result.delta.items)
    assert 'task_changed_since_checkpoint' in result.receipt.stale_context_warnings
