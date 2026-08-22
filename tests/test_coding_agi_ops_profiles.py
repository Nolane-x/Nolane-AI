from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.operations_profiles import OperationsDomain, OperationsProfileRegistry, OperationsWorkRequest
from cogcoder.organization.registry import AgentRegistry


def _request(work_id: str, domain: OperationsDomain, *signals: str):
    return OperationsWorkRequest(
        work_id=work_id, object_id='OPS-OBJECT-1', requested_domains=(domain,),
        scope_hints=tuple(signals), priority=80, requester_agent_id='infrastructure.chief',
        evidence_refs=(f'EV-{work_id}',),
    )


def test_exact_twelve_operational_profiles_split_four_four_four():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = OperationsProfileRegistry(registry)
    rows = profiles.profiles()
    assert len(rows) == 12
    assert sum(x.region == 'data-storage-migration' for x in rows) == 4
    assert sum(x.region == 'infrastructure-release' for x in rows) == 4
    assert sum(x.region == 'performance-reliability' for x in rows) == 4
    assert len({x.domains for x in rows}) == 12
    assert all(registry.get(x.agent_id).learning_capable for x in rows)
    assert all(registry.get(x.agent_id).direct_work_capable for x in rows)


def test_operational_routing_is_domain_specific_and_deterministic():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = OperationsProfileRegistry(registry)
    cases = (
        (OperationsDomain.SCHEMA_MIGRATION, ('schema',), 'data.schema-migration.01'),
        (OperationsDomain.PERSISTENCE, ('transaction',), 'data.persistence.01'),
        (OperationsDomain.CACHE_CONSISTENCY, ('cache',), 'data.cache-consistency.01'),
        (OperationsDomain.CROSS_DATA, ('cross-data',), 'data.chief'),
        (OperationsDomain.CI_ENVIRONMENT, ('ci',), 'infrastructure.ci-env.01'),
        (OperationsDomain.DEPLOYMENT, ('deploy',), 'infrastructure.deployment.01'),
        (OperationsDomain.OBSERVABILITY_RELEASE, ('observability',), 'infrastructure.observability-release.01'),
        (OperationsDomain.CROSS_INFRASTRUCTURE, ('cross-infra',), 'infrastructure.chief'),
        (OperationsDomain.PERFORMANCE, ('profile',), 'reliability.performance.01'),
        (OperationsDomain.CONCURRENCY, ('ordering',), 'reliability.concurrency.01'),
        (OperationsDomain.RECOVERY, ('recovery',), 'reliability.recovery.01'),
        (OperationsDomain.CROSS_RELIABILITY, ('cross-reliability',), 'reliability.chief'),
    )
    for index, (domain, signals, expected) in enumerate(cases):
        request = _request(f'OPS-W-{index}', domain, *signals)
        first = profiles.route(request)
        second = profiles.route(request)
        assert first.selected_agent_id == expected
        assert first == second
        assert first.digest == second.digest


def test_operational_profile_snapshot_tracks_current_neural_version():
    registry = AgentRegistry(build_first_generation_blueprint())
    profiles = OperationsProfileRegistry(registry)
    registry.accept_neural_version('reliability.recovery.01', 'recovery-delta-0.2')
    state = profiles.to_state()
    row = next(x for x in state['profiles'] if x['agent_id'] == 'reliability.recovery.01')
    assert row['accepted_neural_version'] == 'recovery-delta-0.2'
    restored = OperationsProfileRegistry.from_state(registry, state)
    assert restored.get('reliability.recovery.01').accepted_neural_version == 'recovery-delta-0.2'
