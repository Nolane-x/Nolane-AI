import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord, SkillScope


def _candidate(runtime: OrganizationRuntime, agent_id: str = 'coding.backend.01'):
    experience = runtime.individual_evolution.experiences.record(
        agent_id=agent_id, author_agent_id=agent_id, domain='retry-governance',
        outcome='success', summary='bounded idempotent retry works', task_id='T-SKILL',
        object_refs=('src/retry.py',), evidence_refs=('EV-EXP-SKILL',),
    )
    attribution = runtime.individual_evolution.experiences.attribute(
        experience.experience_id, learning_layer='strategy', lesson='bounded idempotent retry',
        evidence=EvidenceRecord('EV-ATTR-SKILL', 'verification.integration-e2e.01', True),
    )
    return runtime.individual_evolution.propose_skill_from_attribution(
        agent_id=agent_id, attribution_id=attribution.attribution_id,
        name='bounded-idempotent-retry', body='Retry only bounded times and require idempotency.',
    )


def _validate_persistent_skill(runtime: OrganizationRuntime, skill_id: str) -> None:
    runtime.learning_substrate.record_skill_validation(
        skill_id,
        regression_evidence_ids=('EV-REGRESSION-A', 'EV-REGRESSION-B'),
        causal_ablation_evidence_ids=('EV-CAUSAL-ABLATION',),
        regression_evidence_families={
            'EV-REGRESSION-A': 'regression-family-a',
            'EV-REGRESSION-B': 'regression-family-b',
        },
        causal_ablation_evidence_families={
            'EV-CAUSAL-ABLATION': 'causal-family',
        },
    )


def test_candidate_skill_is_not_active_and_producer_cannot_self_verify():
    runtime = OrganizationRuntime.first_generation()
    skill = _candidate(runtime)
    assert skill.scope is SkillScope.CANDIDATE
    assert skill.skill_id not in {row.skill_id for row in runtime.evolution.skills_for('coding.backend.01', region='core-coding')}
    with pytest.raises(PermissionError):
        runtime.individual_evolution.verify_skill(skill.skill_id, EvidenceRecord('EV-SELF-SKILL', 'coding.backend.01', True))


def test_skill_promotion_requires_progressively_stronger_external_evidence_and_cross_region_global_evidence():
    runtime = OrganizationRuntime.first_generation()
    skill = _candidate(runtime)
    runtime.individual_evolution.verify_skill(skill.skill_id, EvidenceRecord('EV-V1', 'coding.chief', True))
    _validate_persistent_skill(runtime, skill.skill_id)
    personal = runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)
    assert personal.scope is SkillScope.PERSONAL
    with pytest.raises(PermissionError):
        runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.REGIONAL)

    runtime.individual_evolution.verify_skill(skill.skill_id, EvidenceRecord('EV-V2', 'coding.core-algorithm.01', True))
    regional = runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.REGIONAL)
    assert regional.scope is SkillScope.REGIONAL

    runtime.individual_evolution.verify_skill(skill.skill_id, EvidenceRecord('EV-V3-SAME', 'coding.systems.01', True))
    with pytest.raises(PermissionError):
        runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.GLOBAL)

    runtime.individual_evolution.verify_skill(skill.skill_id, EvidenceRecord('EV-V4-CROSS', 'architecture.chief', True))
    global_skill = runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.GLOBAL)
    assert global_skill.scope is SkillScope.GLOBAL


def test_dirty_skill_evidence_quarantines_candidate_instead_of_promoting_bad_learning():
    runtime = OrganizationRuntime.first_generation()
    skill = _candidate(runtime)
    quarantined = runtime.individual_evolution.verify_skill(
        skill.skill_id, EvidenceRecord('EV-DIRTY', 'verification.fuzz-regression.01', False, false_accepts=1, regressions=1),
    )
    assert quarantined.quarantined is True
    with pytest.raises(PermissionError):
        runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)