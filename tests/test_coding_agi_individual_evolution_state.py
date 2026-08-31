import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord, SkillScope


def test_central_chief_and_specialist_each_own_independent_learning_state():
    runtime = OrganizationRuntime.first_generation()
    for index, agent_id in enumerate(('nolane.central', 'coding.chief', 'coding.backend.01'), start=1):
        experience = runtime.individual_evolution.experiences.record(
            agent_id=agent_id, author_agent_id=agent_id, domain='distributed-learning',
            outcome='success', summary=f'agent-specific lesson {index}', task_id=f'T-DIST-{index}',
            object_refs=(agent_id,), evidence_refs=(f'EV-DIST-{index}',),
        )
        attribution = runtime.individual_evolution.experiences.attribute(
            experience.experience_id, learning_layer='strategy', lesson=f'private strategy {index}',
            evidence=EvidenceRecord(f'EV-DIST-ATTR-{index}', 'verification.integration-e2e.01', True),
        )
        skill = runtime.individual_evolution.propose_skill_from_attribution(
            agent_id=agent_id, attribution_id=attribution.attribution_id,
            name=f'private-skill-{index}', body=f'agent-local procedure {index}',
        )
        assert skill.owner_agent_id == agent_id
        assert skill.scope is SkillScope.CANDIDATE

    assert len(runtime.individual_evolution.experiences.experiences_for('nolane.central')) == 1
    assert len(runtime.individual_evolution.experiences.experiences_for('coding.chief')) == 1
    assert len(runtime.individual_evolution.experiences.experiences_for('coding.backend.01')) == 1


def test_positive_attribution_cannot_be_reassigned_to_another_agent_skill_namespace():
    runtime = OrganizationRuntime.first_generation()
    experience = runtime.individual_evolution.experiences.record(
        agent_id='coding.backend.01', author_agent_id='coding.backend.01', domain='ownership',
        outcome='success', summary='backend-owned lesson', task_id='T-OWN',
        object_refs=('backend',), evidence_refs=('EV-OWN',),
    )
    attribution = runtime.individual_evolution.experiences.attribute(
        experience.experience_id, learning_layer='procedural', lesson='backend-only procedure',
        evidence=EvidenceRecord('EV-OWN-ATTR', 'verification.unit-property.01', True),
    )
    with pytest.raises(PermissionError):
        runtime.individual_evolution.propose_skill_from_attribution(
            agent_id='debug.chief', attribution_id=attribution.attribution_id,
            name='stolen-skill', body='must not cross owner boundary',
        )


def test_runtime_snapshot_restore_preserves_exact_distributed_evolution_state_and_lineage():
    runtime = OrganizationRuntime.first_generation()
    experience = runtime.individual_evolution.experiences.record(
        agent_id='coding.backend.01', author_agent_id='coding.backend.01', domain='snapshot',
        outcome='success', summary='snapshot lesson', task_id='T-SNAPSHOT',
        object_refs=('snapshot',), evidence_refs=('EV-SNAPSHOT',),
    )
    attribution = runtime.individual_evolution.experiences.attribute(
        experience.experience_id, learning_layer='semantic', lesson='snapshot semantics remain exact',
        evidence=EvidenceRecord('EV-SNAPSHOT-ATTR', 'verification.integration-e2e.01', True),
    )
    skill = runtime.individual_evolution.propose_skill_from_attribution(
        agent_id='coding.backend.01', attribution_id=attribution.attribution_id,
        name='snapshot-skill', body='restore evolution state exactly',
    )
    runtime.individual_evolution.verify_skill(
        skill.skill_id, EvidenceRecord('EV-SNAPSHOT-SKILL', 'verification.unit-property.01', True),
    )
    runtime.learning_substrate.record_skill_validation(
        skill.skill_id,
        regression_evidence_ids=('EV-SNAPSHOT-REG-A', 'EV-SNAPSHOT-REG-B'),
        causal_ablation_evidence_ids=('EV-SNAPSHOT-CAUSAL',),
        regression_evidence_families={
            'EV-SNAPSHOT-REG-A': 'snapshot-regression-family-a',
            'EV-SNAPSHOT-REG-B': 'snapshot-regression-family-b',
        },
        causal_ablation_evidence_families={
            'EV-SNAPSHOT-CAUSAL': 'snapshot-causal-family',
        },
    )
    runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)
    runtime.individual_evolution.update_self_model(
        agent_id='coding.backend.01', domain='snapshot', score=0.77,
        evidence=EvidenceRecord('EV-SNAPSHOT-SELF', 'verification.integration-e2e.01', True),
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(state)
    assert restored.to_state() == state
    assert restored.learning_substrate.skills is restored.evolution
    assert restored.learning_substrate.memory is restored.memory
    assert restored.individual_evolution.governed_skill_promoter is restored.learning_substrate
    assert restored.individual_evolution.to_state() == runtime.individual_evolution.to_state()
    assert len(restored.individual_evolution.profiles.profiles()) == 67
    assert restored.individual_evolution.lineage_for('coding.backend.01') == runtime.individual_evolution.lineage_for('coding.backend.01')