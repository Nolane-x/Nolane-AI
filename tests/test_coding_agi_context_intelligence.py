from cogcoder.organization.context_intelligence import ContextBudget, ContextDeltaKind
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind, MemoryScope


def test_context_capsule_exposes_semantic_delta_and_bounded_overload_metrics():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-CONTEXT-1', title='Compile bounded context', plan_node_id='P-CONTEXT-1')
    runtime.tasks.lease('T-CONTEXT-1', 'memory.context-compiler.01')
    for index in range(30):
        runtime.memory.write(
            MemoryScope.REGION, f'context candidate {index} ' + ('z' * 90),
            owner_agent_id='memory.chief', region='memory-context-knowledge', tags=('context',),
            evidence_ids=(f'EV-M-{index}',), confidence=0.6,
        )
    result = runtime.memory_context.compile_context(
        'memory.context-compiler.01', task_id='T-CONTEXT-1',
        budget=ContextBudget(max_memories=4, max_events=4, max_estimated_units=500),
    )
    assert result.capsule.semantic_delta_digest == result.delta.digest
    assert result.capsule.context_compilation_receipt_id == result.receipt.receipt_id
    assert result.capsule.context_budget_units == result.receipt.selected_units
    assert result.capsule.context_overload_ratio == result.receipt.overload_ratio
    assert len(result.capsule.memories) <= 4
    assert result.receipt.memory_candidate_count >= len(result.capsule.memories)
    assert result.receipt.dropped_object_ids


def test_plan_change_and_central_intervention_become_typed_semantic_delta_items():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-CONTEXT-2', title='Track delta', plan_node_id='P-CONTEXT-2')
    runtime.tasks.lease('T-CONTEXT-2', 'coding.backend.01')
    runtime.checkpoint_agent('coding.backend.01')
    checkpoint_id = runtime.memory_context.capture_continuity('coding.backend.01').checkpoint_id

    gap = runtime.report_plan_gap(
        source_agent_id='coding.backend.01', task_id='T-CONTEXT-2',
        reason='need compatibility task', suggested_nodes=('P-COMPAT',), evidence_ids=('EV-GAP',),
    )
    runtime.tasks.apply_plan_amendment('planning.chief', gap.event_id, added_nodes=('P-COMPAT',))
    runtime.central_intervene(
        target_agent_id='coding.backend.01', directive='preserve backward compatibility', evidence_ids=('EV-CENTRAL',),
    )
    result = runtime.memory_context.compile_context(
        'coding.backend.01', continuity_checkpoint_id=checkpoint_id,
        budget=ContextBudget(max_memories=16, max_events=16, max_estimated_units=4096),
    )
    kinds = {item.kind for item in result.delta.items}
    assert ContextDeltaKind.PLAN_CHANGED in kinds
    assert ContextDeltaKind.CENTRAL_INTERVENTION in kinds
    assert result.receipt.stale_context_warnings
