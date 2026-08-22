from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.evolution_profiles import EvolutionProfileRegistry
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.self_model import SelfModelRegistry
from cogcoder.organization.types import EvidenceRecord, PHYSICAL_PARAMETER_CEILING


def test_all_67_permanent_identities_have_learning_manifests_and_unique_personal_namespaces():
    registry = AgentRegistry(build_first_generation_blueprint())
    self_models = SelfModelRegistry(registry)
    profiles = EvolutionProfileRegistry(registry=registry, self_models=self_models)
    rows = profiles.profiles()
    assert len(rows) == 67
    assert len({row.agent_id for row in rows}) == 67
    assert len({row.memory_namespace for row in rows}) == 67
    assert len({row.skill_namespace for row in rows}) == 67
    assert all(row.learning_capable for row in rows)
    assert all(row.physical_parameters < PHYSICAL_PARAMETER_CEILING for row in rows)
    assert all(row.self_model_version == self_models.get(row.agent_id).version for row in rows)


def test_specialization_signature_stays_stable_when_neural_and_self_model_versions_advance():
    registry = AgentRegistry(build_first_generation_blueprint())
    self_models = SelfModelRegistry(registry)
    profiles = EvolutionProfileRegistry(registry=registry, self_models=self_models)
    before = profiles.get('coding.backend.01')
    signature = before.specialization_signature

    self_models.update_competence(
        'coding.backend.01', domain='backend', score=0.81,
        evidence=EvidenceRecord('EV-EXT', 'verification.unit-property.01', True),
    )
    registry.accept_neural_version('coding.backend.01', 'backend-delta-0.2')
    after = profiles.get('coding.backend.01')
    assert after.specialization_signature == signature
    assert after.neural_version == 'backend-delta-0.2'
    assert after.self_model_version != before.self_model_version
    assert after.memory_namespace == before.memory_namespace
    assert after.skill_namespace == before.skill_namespace
