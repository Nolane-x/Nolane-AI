from cogcoder.organization.assurance_profiles import AssuranceDomain, AssuranceProfileRegistry, AssuranceWorkRequest
from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.registry import AgentRegistry


def _request(work_id: str, domain: AssuranceDomain, *signals: str):
    return AssuranceWorkRequest(
        work_id=work_id, subject_id='SUBJECT-1', requested_domains=(domain,),
        scope_hints=tuple(signals), priority=80, requester_agent_id='verification.chief',
        evidence_refs=(f'EV-{work_id}',),
    )


def test_exact_nine_assurance_profiles_split_verification_and_security():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = AssuranceProfileRegistry(registry)
    rows = profiles.profiles()
    assert len(rows) == 9
    assert sum(x.region == 'verification-testing' for x in rows) == 5
    assert sum(x.region == 'security-adversarial' for x in rows) == 4
    assert len({x.domains for x in rows}) == 9
    assert all(registry.get(x.agent_id).learning_capable for x in rows)
    assert all(registry.get(x.agent_id).direct_work_capable for x in rows)


def test_assurance_routing_is_domain_specific_and_deterministic():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = AssuranceProfileRegistry(registry)
    cases = (
        (AssuranceDomain.UNIT_PROPERTY, ('property',), 'verification.unit-property.01'),
        (AssuranceDomain.INTEGRATION_E2E, ('e2e',), 'verification.integration-e2e.01'),
        (AssuranceDomain.SPEC_ACCEPTANCE, ('acceptance',), 'verification.spec-acceptance.01'),
        (AssuranceDomain.FUZZ_REGRESSION, ('fuzz',), 'verification.fuzz-regression.01'),
        (AssuranceDomain.THREAT_MODEL, ('trust-boundary',), 'security.threat-model.01'),
        (AssuranceDomain.SUPPLY_CHAIN, ('dependency',), 'security.supply-chain.01'),
        (AssuranceDomain.ADVERSARIAL, ('attack',), 'security.adversarial.01'),
        (AssuranceDomain.CROSS_VERIFICATION, ('cross-domain',), 'verification.chief'),
        (AssuranceDomain.CROSS_SECURITY, ('cross-threat',), 'security.chief'),
    )
    for index, (domain, signals, expected) in enumerate(cases):
        request = _request(f'W-{index}', domain, *signals)
        first = profiles.route(request)
        second = profiles.route(request)
        assert first.selected_agent_id == expected
        assert first == second
        assert first.digest == second.digest


def test_assurance_profile_snapshot_tracks_current_neural_version():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = AssuranceProfileRegistry(registry)
    registry.accept_neural_version('security.adversarial.01', 'security-adversarial-delta-0.2')
    state = profiles.to_state()
    row = next(x for x in state['profiles'] if x['agent_id'] == 'security.adversarial.01')
    assert row['accepted_neural_version'] == 'security-adversarial-delta-0.2'
    restored = AssuranceProfileRegistry.from_state(registry, state)
    assert restored.get('security.adversarial.01').accepted_neural_version == 'security-adversarial-delta-0.2'
