from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.ui_profiles import UIDomain, UIProfileRegistry, UIWorkRequest


def _request(work_id: str, domain: UIDomain, *signals: str) -> UIWorkRequest:
    return UIWorkRequest(
        work_id=work_id,
        task_id=f'T-{work_id}',
        requested_domains=(domain,),
        scope_hints=tuple(signals),
        priority=60,
        requester_agent_id='frontend.chief',
        evidence_refs=(f'EV-{work_id}',),
    )


def test_exact_seven_ui_ux_profiles_with_distinct_regions_and_domains():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = UIProfileRegistry(registry)
    rows = profiles.profiles()
    assert len(rows) == 7
    assert sum(row.region == 'frontend-ui' for row in rows) == 4
    assert sum(row.region == 'ux-product-design' for row in rows) == 3
    assert len({row.domains for row in rows}) == 7
    for row in rows:
        identity = registry.get(row.agent_id)
        assert identity.learning_capable is True
        assert identity.direct_work_capable is True


def test_ui_routing_is_role_specific_and_deterministic():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = UIProfileRegistry(registry)
    cases = (
        (UIDomain.FRONTEND_LOGIC, ('state', 'data-flow'), 'frontend.logic.01'),
        (UIDomain.COMPONENT, ('component', 'design-system'), 'frontend.component.01'),
        (UIDomain.BROWSER_RUNTIME, ('dom', 'runtime'), 'frontend.browser-runtime.01'),
        (UIDomain.UX_FLOW, ('journey', 'interaction'), 'ux.flow.01'),
        (UIDomain.VISUAL_ACCESSIBILITY, ('accessibility', 'responsive'), 'ux.visual-accessibility.01'),
        (UIDomain.FRONTEND_CROSS_SYSTEM, ('cross-frontend', 'integration'), 'frontend.chief'),
        (UIDomain.UX_CROSS_PRODUCT, ('cross-product', 'acceptance'), 'ux.chief'),
    )
    for index, (domain, signals, expected) in enumerate(cases):
        request = _request(f'W-{index}', domain, *signals)
        first = profiles.route(request)
        second = profiles.route(request)
        assert first.selected_agent_id == expected
        assert first == second
        assert first.digest == second.digest


def test_profile_state_tracks_authoritative_current_neural_version():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = UIProfileRegistry(registry)
    registry.accept_neural_version('frontend.browser-runtime.01', 'browser-runtime-delta-0.2')
    state = profiles.to_state()
    row = next(x for x in state['profiles'] if x['agent_id'] == 'frontend.browser-runtime.01')
    assert row['accepted_neural_version'] == 'browser-runtime-delta-0.2'
    restored = UIProfileRegistry.from_state(registry, state)
    assert restored.get('frontend.browser-runtime.01').accepted_neural_version == 'browser-runtime-delta-0.2'
