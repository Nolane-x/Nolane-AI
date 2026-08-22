from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.coding_profiles import (
    CodingDomain,
    CodingProfileRegistry,
    CodingWorkRequest,
)


def _request(work_id: str, domain: CodingDomain, *signals: str) -> CodingWorkRequest:
    return CodingWorkRequest(
        work_id=work_id,
        task_id=f'T-{work_id}',
        plan_node_id='P-1',
        requirement_refs=('REQ-1',),
        architecture_version=3,
        plan_version=5,
        requested_domains=(domain,),
        scope_hints=tuple(signals),
        acceptance_refs=('AC-1',),
        priority=50,
        requester_agent_id='coding.chief',
        evidence_refs=('EV-ROUTE-1',),
    )


def test_exactly_seven_persistent_coding_profiles_remain_general_learning_agents():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = CodingProfileRegistry(registry)
    rows = profiles.profiles()

    assert len(rows) == 7
    assert {row.agent_id for row in rows} == {
        'coding.chief',
        'coding.core-algorithm.01',
        'coding.backend.01',
        'coding.systems.01',
        'coding.refactor.01',
        'coding.api-interface.01',
        'coding.build-dependency.01',
    }
    assert all(registry.get(row.agent_id).learning_capable for row in rows)
    assert all(registry.get(row.agent_id).direct_work_capable for row in rows)
    assert all('local_planning' in registry.get(row.agent_id).cognitive_capabilities for row in rows)
    assert len({row.domains for row in rows}) > 1
    assert all(row.preferred_external_cores for row in rows)


def test_router_is_specialized_and_deterministic():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = CodingProfileRegistry(registry)

    backend = profiles.route(_request('BACKEND', CodingDomain.BACKEND, 'service', 'api'))
    systems = profiles.route(_request('SYSTEMS', CodingDomain.SYSTEMS, 'runtime', 'concurrency'))
    chief = profiles.route(_request('CHIEF', CodingDomain.CROSS_SYSTEM, 'cross-system', 'integration'))

    assert backend.selected_agent_id == 'coding.backend.01'
    assert systems.selected_agent_id == 'coding.systems.01'
    assert chief.selected_agent_id == 'coding.chief'

    replay = profiles.route(_request('BACKEND', CodingDomain.BACKEND, 'service', 'api'))
    assert replay.ranked_candidates == backend.ranked_candidates
    assert replay.digest == backend.digest
