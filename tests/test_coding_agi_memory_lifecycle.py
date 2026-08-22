import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.events import EventLedger
from cogcoder.organization.memory import MemoryFabric
from cogcoder.organization.memory_lifecycle import (
    MemoryLifecycleLedger,
    MemoryRelationGraph,
    MemoryRelationKind,
)
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.types import MemoryScope, MemoryStatus


def _parts():
    registry = AgentRegistry(build_first_generation_blueprint())
    memory = MemoryFabric()
    events = EventLedger()
    lifecycle = MemoryLifecycleLedger(registry=registry, memory=memory, events=events)
    relations = MemoryRelationGraph(registry=registry, memory=memory, events=events)
    return registry, memory, events, lifecycle, relations


def test_only_memory_region_can_perform_privileged_lifecycle_transition_and_history_is_preserved():
    _, memory, _, lifecycle, _ = _parts()
    row = memory.write(
        MemoryScope.PERSONAL, 'old contract uses v1', owner_agent_id='coding.backend.01',
        tags=('api-contract',), evidence_ids=('EV-OLD',), confidence=1.0,
    )
    with pytest.raises(PermissionError):
        lifecycle.transition(
            row.memory_id, actor_agent_id='coding.backend.01', new_status=MemoryStatus.QUARANTINED,
            reason='hide my own failure', evidence_refs=('EV-X',),
        )
    receipt = lifecycle.transition(
        row.memory_id, actor_agent_id='memory.lifecycle.01', new_status=MemoryStatus.QUARANTINED,
        reason='contradicted by newer verified contract', evidence_refs=('EV-NEW',),
    )
    assert receipt.previous_status is MemoryStatus.ACTIVE
    assert receipt.new_status is MemoryStatus.QUARANTINED
    assert memory.get(row.memory_id).status is MemoryStatus.QUARANTINED
    assert lifecycle.receipts_for(row.memory_id) == (receipt,)


def test_reactivation_requires_memory_chief_and_explicit_corrective_evidence():
    _, memory, _, lifecycle, _ = _parts()
    row = memory.write(MemoryScope.PERSONAL, 'temporarily unsafe memory', owner_agent_id='coding.backend.01')
    lifecycle.transition(
        row.memory_id, actor_agent_id='memory.lifecycle.01', new_status=MemoryStatus.QUARANTINED,
        reason='unsafe until corrected', evidence_refs=('EV-BLOCK',),
    )
    with pytest.raises(PermissionError):
        lifecycle.transition(
            row.memory_id, actor_agent_id='memory.lifecycle.01', new_status=MemoryStatus.ACTIVE,
            reason='looks fine now', evidence_refs=('EV-MAYBE',), correction_ref='CORR-1',
        )
    with pytest.raises(ValueError):
        lifecycle.transition(
            row.memory_id, actor_agent_id='memory.chief', new_status=MemoryStatus.ACTIVE,
            reason='corrected', evidence_refs=('EV-CORRECT',), correction_ref=None,
        )
    active = lifecycle.transition(
        row.memory_id, actor_agent_id='memory.chief', new_status=MemoryStatus.ACTIVE,
        reason='corrected using verified replacement evidence', evidence_refs=('EV-CORRECT',), correction_ref='CORR-1',
    )
    assert active.new_status is MemoryStatus.ACTIVE
    assert len(lifecycle.receipts_for(row.memory_id)) == 2


def test_relation_graph_is_immutable_typed_and_cannot_use_unknown_or_invalid_self_edges():
    _, memory, _, _, relations = _parts()
    old = memory.write(MemoryScope.PERSONAL, 'v1', owner_agent_id='coding.backend.01')
    new = memory.write(MemoryScope.PERSONAL, 'v2', owner_agent_id='coding.backend.01')
    edge = relations.add(
        actor_agent_id='memory.knowledge-graph.01', source_memory_id=new.memory_id,
        target_memory_id=old.memory_id, kind=MemoryRelationKind.CONTRADICTS,
        evidence_refs=('EV-CONTRADICTION',),
    )
    assert edge.kind is MemoryRelationKind.CONTRADICTS
    with pytest.raises(KeyError):
        relations.add(
            actor_agent_id='memory.knowledge-graph.01', source_memory_id='mem-99999999',
            target_memory_id=old.memory_id, kind=MemoryRelationKind.SUPPORTS, evidence_refs=('EV-X',),
        )
    with pytest.raises(ValueError):
        relations.add(
            actor_agent_id='memory.knowledge-graph.01', source_memory_id=old.memory_id,
            target_memory_id=old.memory_id, kind=MemoryRelationKind.CONTRADICTS, evidence_refs=('EV-X',),
        )
    state = relations.to_state()
    restored = MemoryRelationGraph.from_state(
        registry=relations.registry, memory=memory, events=relations.events, state=state,
    )
    assert restored.to_state() == state
