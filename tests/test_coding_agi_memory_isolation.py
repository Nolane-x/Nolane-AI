from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.events import EventLedger
from cogcoder.organization.memory import MemoryFabric
from cogcoder.organization.memory_lifecycle import MemoryRelationGraph, MemoryRelationKind
from cogcoder.organization.memory_retrieval import MemoryRetrievalBudget, MemoryRetrievalEngine
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.types import MemoryScope, MemoryStatus


def _engine():
    registry = AgentRegistry(build_first_generation_blueprint())
    memory = MemoryFabric()
    events = EventLedger()
    relations = MemoryRelationGraph(registry=registry, memory=memory, events=events)
    return registry, memory, relations, MemoryRetrievalEngine(memory=memory, relations=relations)


def test_scope_isolation_happens_before_ranking_and_private_personal_memory_never_leaks():
    _, memory, _, engine = _engine()
    private = memory.write(
        MemoryScope.PRIVATE, 'secret root cause', owner_agent_id='coding.backend.01',
        tags=('critical', 'root-cause'), confidence=1.0,
    )
    personal = memory.write(
        MemoryScope.PERSONAL, 'personal coding heuristic', owner_agent_id='coding.backend.01',
        tags=('critical',), confidence=1.0,
    )
    global_row = memory.write(
        MemoryScope.GLOBAL, 'shared verified fact', owner_agent_id='memory.chief',
        tags=('critical',), confidence=0.5,
    )
    receipt = engine.select(
        agent_id='debug.chief', region='debugging-failure', task_id=None,
        tags=('critical',), budget=MemoryRetrievalBudget(max_memories=32, max_estimated_units=4096),
    )
    assert private.memory_id not in receipt.candidate_memory_ids
    assert personal.memory_id not in receipt.candidate_memory_ids
    assert global_row.memory_id in receipt.selected_memory_ids


def test_relation_to_visible_memory_cannot_broaden_private_memory_visibility():
    _, memory, relations, engine = _engine()
    public = memory.write(MemoryScope.GLOBAL, 'public interface', owner_agent_id='memory.chief')
    secret = memory.write(MemoryScope.PRIVATE, 'private exploit hypothesis', owner_agent_id='security.chief')
    relations.add(
        actor_agent_id='memory.knowledge-graph.01', source_memory_id=secret.memory_id,
        target_memory_id=public.memory_id, kind=MemoryRelationKind.DEPENDS_ON,
        evidence_refs=('EV-REL',),
    )
    receipt = engine.select(
        agent_id='coding.backend.01', region='core-coding', task_id=None,
        tags=(), budget=MemoryRetrievalBudget(max_memories=32, max_estimated_units=4096),
    )
    assert public.memory_id in receipt.selected_memory_ids
    assert secret.memory_id not in receipt.candidate_memory_ids


def test_inactive_high_confidence_exact_match_cannot_poison_normal_retrieval():
    _, memory, _, engine = _engine()
    poisoned = memory.write(
        MemoryScope.GLOBAL, 'API version is definitely v1', owner_agent_id='memory.chief',
        tags=('api-version',), confidence=1.0,
    )
    memory.set_status(poisoned.memory_id, MemoryStatus.CONTRADICTED, reason='verified v2 replaced it')
    current = memory.write(
        MemoryScope.GLOBAL, 'API version is v2', owner_agent_id='memory.chief',
        tags=('api-version',), confidence=0.7,
    )
    receipt = engine.select(
        agent_id='coding.backend.01', region='core-coding', task_id=None,
        tags=('api-version',), budget=MemoryRetrievalBudget(max_memories=8, max_estimated_units=1024),
    )
    assert poisoned.memory_id not in receipt.candidate_memory_ids
    assert current.memory_id in receipt.selected_memory_ids


def test_retrieval_budget_is_deterministic_and_records_drops():
    _, memory, _, engine = _engine()
    for index in range(12):
        memory.write(
            MemoryScope.GLOBAL, f'bounded memory {index} ' + ('x' * 80), owner_agent_id='memory.chief',
            tags=('overload',), confidence=0.5 + index / 100,
        )
    budget = MemoryRetrievalBudget(max_memories=3, max_estimated_units=300)
    first = engine.select(agent_id='coding.backend.01', region='core-coding', task_id=None, tags=('overload',), budget=budget)
    second = engine.select(agent_id='coding.backend.01', region='core-coding', task_id=None, tags=('overload',), budget=budget)
    assert first.selected_memory_ids == second.selected_memory_ids
    assert first.selected_units <= budget.max_estimated_units
    assert len(first.selected_memory_ids) <= budget.max_memories
    assert first.dropped_memory_ids
    assert first.drop_reasons
