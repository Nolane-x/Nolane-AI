from cogcoder.organization.memory_lifecycle import MemoryRelationKind
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.snapshot import OrganizationSnapshot
from cogcoder.organization.types import MemoryScope, MemoryStatus


def test_memory_context_state_round_trips_exactly_through_organization_snapshot():
    runtime = OrganizationRuntime.first_generation()
    old = runtime.memory.write(
        MemoryScope.REGION, 'region assumption v1', owner_agent_id='memory.chief',
        region='memory-context-knowledge', evidence_ids=('EV-OLD',),
    )
    new = runtime.memory.write(
        MemoryScope.REGION, 'region assumption v2', owner_agent_id='memory.chief',
        region='memory-context-knowledge', evidence_ids=('EV-NEW',),
    )
    runtime.memory_context.relations.add(
        actor_agent_id='memory.knowledge-graph.01', source_memory_id=new.memory_id,
        target_memory_id=old.memory_id, kind=MemoryRelationKind.SUPERSEDES,
        evidence_refs=('EV-NEW',),
    )
    runtime.memory_context.lifecycle.transition(
        old.memory_id, actor_agent_id='memory.lifecycle.01', new_status=MemoryStatus.SUPERSEDED,
        reason='replaced by v2', evidence_refs=('EV-NEW',),
    )
    runtime.checkpoint_agent('memory.context-compiler.01')
    runtime.memory_context.capture_continuity('memory.context-compiler.01')

    before = runtime.to_state()
    snapshot = OrganizationSnapshot.capture(runtime)
    restored = snapshot.restore()
    assert restored.to_state() == before
    assert restored.memory_context.to_state() == runtime.memory_context.to_state()


def test_memory_intelligence_private_state_is_only_exposed_to_memory_region():
    runtime = OrganizationRuntime.first_generation()
    memory_capsule = runtime.context.compile('memory.chief')
    coding_capsule = runtime.context.compile('coding.backend.01')
    research_capsule = runtime.context.compile('research.chief')
    assert ('memory-intelligence-state', runtime.memory_context.digest) in memory_capsule.authoritative_artifacts
    assert all(name != 'memory-intelligence-state' for name, _ in coding_capsule.authoritative_artifacts)
    assert all(name != 'memory-intelligence-state' for name, _ in research_capsule.authoritative_artifacts)


def test_runtime_state_without_part_xi_key_restores_with_empty_additive_control_plane():
    runtime = OrganizationRuntime.first_generation()
    state = runtime.to_state()
    state.pop('memory_context')
    restored = OrganizationRuntime.from_state(state)
    assert restored.memory_context.to_state()['lifecycle']['receipts'] == []
    assert restored.memory_context.to_state()['relations']['relations'] == []
