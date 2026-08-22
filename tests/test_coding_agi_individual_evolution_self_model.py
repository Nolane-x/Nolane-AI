import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord


def test_self_model_improvement_requires_external_clean_evidence_and_preserves_specialization():
    runtime = OrganizationRuntime.first_generation()
    agent_id = 'coding.backend.01'
    before_profile = runtime.individual_evolution.profiles.get(agent_id)
    before_lineage = runtime.individual_evolution.lineage_for(agent_id)

    with pytest.raises(PermissionError):
        runtime.individual_evolution.update_self_model(
            agent_id=agent_id, domain='backend', score=0.82,
            evidence=EvidenceRecord('EV-SELF-MODEL-SELF', agent_id, True),
        )

    updated = runtime.individual_evolution.update_self_model(
        agent_id=agent_id, domain='backend', score=0.82,
        evidence=EvidenceRecord('EV-SELF-MODEL-EXT', 'verification.unit-property.01', True),
    )
    after_profile = runtime.individual_evolution.profiles.get(agent_id)
    assert updated.version != before_profile.self_model_version
    assert after_profile.self_model_version == updated.version
    assert after_profile.specialization_signature == before_profile.specialization_signature
    assert len(runtime.individual_evolution.lineage_for(agent_id)) == len(before_lineage) + 1
    assert runtime.individual_evolution.lineage_for(agent_id)[-1].transition == 'self_model_updated'


def test_dirty_external_evidence_cannot_raise_self_model_competence():
    runtime = OrganizationRuntime.first_generation()
    agent_id = 'debug.runtime-trace.01'
    before = runtime.self_models.get(agent_id)
    with pytest.raises(PermissionError):
        runtime.individual_evolution.update_self_model(
            agent_id=agent_id, domain='runtime-debugging', score=0.9,
            evidence=EvidenceRecord('EV-SELF-MODEL-BAD', 'verification.fuzz-regression.01', True, regressions=1),
        )
    assert runtime.self_models.get(agent_id) == before
