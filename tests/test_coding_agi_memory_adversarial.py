from cogcoder.organization.context_intelligence import ContextBudget
from cogcoder.organization.memory_lifecycle import MemoryRelationKind
from cogcoder.organization.memory_retrieval import MemoryRetrievalBudget
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind, MemoryScope, MemoryStatus


def test_private_and_task_memory_cannot_leak_under_similarity_relation_or_overload_pressure():
    runtime = OrganizationRuntime.first_generation()
    private = runtime.memory.write(
        MemoryScope.PRIVATE, 'critical token secret', owner_agent_id='security.chief',
        tags=('critical', 'shared'), confidence=1.0,
    )
    task_private = runtime.memory.write(
        MemoryScope.TASK, 'task A hidden state', owner_agent_id='coding.backend.01', task_id='T-A',
        tags=('critical', 'shared'), confidence=1.0,
    )
    visible = runtime.memory.write(
        MemoryScope.GLOBAL, 'public critical guidance', owner_agent_id='memory.chief',
        tags=('critical', 'shared'), confidence=0.4,
    )
    runtime.memory_context.relations.add(
        actor_agent_id='memory.knowledge-graph.01', source_memory_id=private.memory_id,
        target_memory_id=visible.memory_id, kind=MemoryRelationKind.SUPPORTS,
        evidence_refs=('EV-REL',),
    )
    receipt = runtime.memory_context.retrieval.select(
        agent_id='coding.backend.01', region='core-coding', task_id='T-B', tags=('critical', 'shared'),
        budget=MemoryRetrievalBudget(max_memories=2, max_estimated_units=128),
    )
    assert private.memory_id not in receipt.candidate_memory_ids
    assert task_private.memory_id not in receipt.candidate_memory_ids
    assert visible.memory_id in receipt.selected_memory_ids


def test_stale_contradicted_and_quarantined_memories_never_reenter_context_under_high_confidence():
    runtime = OrganizationRuntime.first_generation()
    rows = []
    for status in (MemoryStatus.STALE, MemoryStatus.CONTRADICTED, MemoryStatus.QUARANTINED):
        row = runtime.memory.write(
            MemoryScope.GLOBAL, f'poison-{status.value}', owner_agent_id='memory.chief',
            tags=('poison',), confidence=1.0,
        )
        runtime.memory_context.lifecycle.transition(
            row.memory_id, actor_agent_id='memory.lifecycle.01', new_status=status,
            reason=f'adversarial {status.value} memory', evidence_refs=(f'EV-{status.value}',),
        )
        rows.append(row)
    good = runtime.memory.write(
        MemoryScope.GLOBAL, 'verified-current', owner_agent_id='memory.chief',
        tags=('poison',), confidence=0.5, evidence_ids=('EV-GOOD',),
    )
    result = runtime.memory_context.compile_context(
        'coding.backend.01', budget=ContextBudget(max_memories=8, max_events=8, max_estimated_units=2048),
    )
    selected = {row.memory_id for row in result.capsule.memories}
    assert good.memory_id in selected
    assert selected.isdisjoint({row.memory_id for row in rows})


def test_huge_history_is_measured_and_bounded_without_unfiltered_fallback():
    runtime = OrganizationRuntime.first_generation()
    for index in range(120):
        runtime.ledger.append(
            EventKind.EVIDENCE_ADDED, source_agent_id='coding.backend.01', target_agent_id='coding.backend.01',
            region='core-coding', payload={'index': index, 'blob': 'x' * 120}, evidence_refs=(f'EV-{index}',),
        )
    result = runtime.memory_context.compile_context(
        'coding.backend.01', budget=ContextBudget(max_memories=4, max_events=5, max_estimated_units=700),
    )
    assert result.receipt.event_candidate_count >= 100
    assert result.receipt.selected_event_count <= 5
    assert result.receipt.dropped_event_count > 0
    assert result.receipt.overload_ratio > 1.0
    assert len(result.capsule.event_delta) <= 5
