from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.memory_profiles import (
    MemoryIntelligenceDomain,
    MemoryIntelligenceProfileRegistry,
    MemoryWorkRequest,
)
from cogcoder.organization.registry import AgentRegistry


def _request(work_id, domain, requester='coding.backend.01', *signals):
    return MemoryWorkRequest(
        work_id=work_id,
        object_id=f'object-{work_id}',
        requested_domains=(domain,),
        scope_hints=tuple(signals),
        priority=80,
        requester_agent_id=requester,
        evidence_refs=(f'EV-{work_id}',),
    )


def test_exact_four_memory_profiles_and_deterministic_cross_region_routing():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = MemoryIntelligenceProfileRegistry(registry)
    rows = profiles.profiles()
    assert len(rows) == 4
    assert {row.agent_id for row in rows} == {
        'memory.chief',
        'memory.context-compiler.01',
        'memory.knowledge-graph.01',
        'memory.lifecycle.01',
    }
    assert all(row.region == 'memory-context-knowledge' for row in rows)
    assert profiles.route(_request('M-1', MemoryIntelligenceDomain.LIFECYCLE, 'debug.chief', 'quarantine')).selected_agent_id == 'memory.lifecycle.01'
    assert profiles.route(_request('M-2', MemoryIntelligenceDomain.KNOWLEDGE_GRAPH, 'research.chief', 'contradiction')).selected_agent_id == 'memory.knowledge-graph.01'
    assert profiles.route(_request('M-3', MemoryIntelligenceDomain.CONTEXT_COMPILATION, 'planning.chief', 'context')).selected_agent_id == 'memory.context-compiler.01'
    assert profiles.route(_request('M-4', MemoryIntelligenceDomain.CROSS_MEMORY, 'nolane.central', 'repair')).selected_agent_id == 'memory.chief'


def test_memory_profile_snapshot_tracks_current_neural_version():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = MemoryIntelligenceProfileRegistry(registry)
    registry.accept_neural_version('memory.context-compiler.01', 'context-delta-0.2')
    state = profiles.to_state()
    row = next(x for x in state['profiles'] if x['agent_id'] == 'memory.context-compiler.01')
    assert row['accepted_neural_version'] == 'context-delta-0.2'
    restored = MemoryIntelligenceProfileRegistry.from_state(registry, state)
    assert restored.get('memory.context-compiler.01').accepted_neural_version == 'context-delta-0.2'
