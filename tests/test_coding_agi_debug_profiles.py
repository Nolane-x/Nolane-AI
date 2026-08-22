from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.debug_profiles import DebugDomain, DebugProfileRegistry, DebugWorkRequest
from cogcoder.organization.registry import AgentRegistry


def _request(work_id, domain, *signals):
    return DebugWorkRequest(
        work_id=work_id,
        case_id=f'CASE-{work_id}',
        task_id=f'T-{work_id}',
        requested_domains=(domain,),
        scope_hints=tuple(signals),
        priority=50,
        requester_agent_id='debug.chief',
        evidence_refs=('EV-DEBUG-ROUTE',),
    )


def test_exactly_six_debug_profiles_are_distinct_general_learning_agents():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = DebugProfileRegistry(registry)
    rows = profiles.profiles()
    assert len(rows) == 6
    assert {row.agent_id for row in rows} == {
        'debug.chief', 'debug.reproducer.01', 'debug.runtime-trace.01',
        'debug.static-root-cause.01', 'debug.concurrency-state.01', 'debug.regression-bisect.01',
    }
    assert all(registry.get(row.agent_id).learning_capable for row in rows)
    assert all(registry.get(row.agent_id).direct_work_capable for row in rows)
    assert all('causal_reasoning' in registry.get(row.agent_id).cognitive_capabilities for row in rows)
    assert len({row.domains for row in rows}) == 6
    assert all(row.preferred_external_cores for row in rows)


def test_debug_router_uses_distinct_specializations_and_is_deterministic():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = DebugProfileRegistry(registry)
    expected = (
        (DebugDomain.REPRODUCTION, 'debug.reproducer.01', ('reproduce', 'minimize')),
        (DebugDomain.RUNTIME_TRACE, 'debug.runtime-trace.01', ('trace', 'stack')),
        (DebugDomain.STATIC_ROOT_CAUSE, 'debug.static-root-cause.01', ('static', 'data-flow')),
        (DebugDomain.CONCURRENCY_STATE, 'debug.concurrency-state.01', ('race', 'deadlock')),
        (DebugDomain.REGRESSION_BISECT, 'debug.regression-bisect.01', ('regression', 'bisect')),
        (DebugDomain.CROSS_FAILURE, 'debug.chief', ('cross-failure', 'mixed')),
    )
    for index, (domain, agent_id, signals) in enumerate(expected):
        request = _request(str(index), domain, *signals)
        receipt = profiles.route(request)
        assert receipt.selected_agent_id == agent_id
        replay = profiles.route(request)
        assert replay.ranked_candidates == receipt.ranked_candidates
        assert replay.digest == receipt.digest
