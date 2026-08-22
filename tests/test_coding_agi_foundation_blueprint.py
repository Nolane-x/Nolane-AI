import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint, validate_blueprint
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.types import AgentRank, AgentStatus, ParameterAccounting


def test_first_generation_blueprint_has_exact_organization_shape():
    identities = build_first_generation_blueprint()
    validate_blueprint(identities)

    assert len(identities) == 67
    assert sum(row.rank is AgentRank.CENTRAL for row in identities) == 1
    assert sum(row.rank is AgentRank.CHIEF for row in identities) == 15
    assert sum(row.rank in (AgentRank.SENIOR_SPECIALIST, AgentRank.SPECIALIST) for row in identities) == 51

    regions = {row.region for row in identities if row.rank is not AgentRank.CENTRAL}
    assert regions == {
        'requirements-product',
        'planning-program',
        'architecture-system',
        'core-coding',
        'frontend-ui',
        'ux-product-design',
        'debugging-failure',
        'verification-testing',
        'security-adversarial',
        'data-storage-migration',
        'infrastructure-release',
        'performance-reliability',
        'research-external',
        'integration-change-control',
        'memory-context-knowledge',
    }

    for row in identities:
        assert row.learning_capable is True
        assert row.parameter_accounting.total_physical_parameters < 100_000_000
        if row.rank is AgentRank.CHIEF:
            assert row.direct_work_capable is True
            assert 82_000_000 <= row.parameter_accounting.total_physical_parameters <= 94_000_000
        if row.rank is AgentRank.CENTRAL:
            assert row.direct_work_capable is True
            assert 90_000_000 <= row.parameter_accounting.total_physical_parameters <= 98_000_000


def test_parameter_accounting_is_physical_and_fail_closed_at_100m():
    ok = ParameterAccounting(shared_physical_parameters=56_000_000, local_physical_parameters=35_000_000)
    assert ok.total_physical_parameters == 91_000_000

    with pytest.raises(ValueError, match='below 100,000,000'):
        ParameterAccounting(shared_physical_parameters=56_000_000, local_physical_parameters=44_000_000)


def test_registry_rejects_duplicate_identity_and_preserves_accepted_version_on_restart():
    identities = build_first_generation_blueprint()
    registry = AgentRegistry(identities)
    backend = registry.get('coding.backend.01')
    assert backend.status is AgentStatus.SLEEPING

    with pytest.raises(ValueError, match='duplicate agent id'):
        registry.register(backend)

    registry.set_status(backend.agent_id, AgentStatus.ACTIVE)
    registry.bind_task(backend.agent_id, 'T-184')
    registry.accept_neural_version(backend.agent_id, 'backend-delta-0.4')

    restored = AgentRegistry.from_state(registry.to_state())
    row = restored.get(backend.agent_id)
    assert row.status is AgentStatus.ACTIVE
    assert row.current_task == 'T-184'
    assert row.neural_version == 'backend-delta-0.4'
    assert 'backend-delta-0.4' in restored.accepted_versions(backend.agent_id)
