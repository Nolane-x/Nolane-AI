import pytest

from cogcoder.organization.evolution import SkillEvolutionEngine
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord, SkillScope
from cogcoder.organization.verification import CandidateEvaluation


def _evidence(evidence_id, verifier, *, passed=True, false_accepts=0, regressions=0):
    return EvidenceRecord(
        evidence_id=evidence_id,
        verifier_agent_id=verifier,
        passed=passed,
        false_accepts=false_accepts,
        regressions=regressions,
        notes='focused verification',
    )


def test_skill_candidate_is_inactive_until_verified_and_can_promote_personal_regional_global():
    engine = SkillEvolutionEngine()
    skill = engine.propose(
        owner_agent_id='debug.runtime-trace.01',
        region='debugging-failure',
        name='mutable-state-recheck',
        body='Re-read mutable state at the authority boundary before accepting a root-cause hypothesis.',
    )
    assert engine.skills_for('debug.runtime-trace.01', region='debugging-failure') == ()

    engine.verify(skill.skill_id, _evidence('EV-1', 'verification.unit-property.01'))
    personal = engine.promote(skill.skill_id, SkillScope.PERSONAL)
    assert personal in engine.skills_for('debug.runtime-trace.01', region='debugging-failure')

    engine.verify(skill.skill_id, _evidence('EV-2', 'verification.integration-e2e.01'))
    regional = engine.promote(skill.skill_id, SkillScope.REGIONAL)
    assert regional.scope is SkillScope.REGIONAL

    engine.verify(skill.skill_id, _evidence('EV-3', 'verification.spec-acceptance.01'))
    global_skill = engine.promote(skill.skill_id, SkillScope.GLOBAL)
    assert global_skill.scope is SkillScope.GLOBAL


def test_quarantined_skill_keeps_provenance_but_is_not_retrieved():
    engine = SkillEvolutionEngine()
    skill = engine.propose(owner_agent_id='coding.backend.01', region='core-coding', name='bad-rule', body='candidate rule')
    engine.verify(skill.skill_id, _evidence('EV-1', 'verification.unit-property.01'))
    engine.promote(skill.skill_id, SkillScope.PERSONAL)
    engine.quarantine(skill.skill_id, reason='counterexample found')
    assert engine.get(skill.skill_id).quarantined is True
    assert engine.skills_for('coding.backend.01', region='core-coding') == ()


def test_neural_challenger_promotion_is_fail_closed_and_exactly_rollbackable():
    runtime = OrganizationRuntime.first_generation()
    agent_id = 'coding.backend.01'
    original = runtime.registry.get(agent_id).neural_version

    bad = CandidateEvaluation(
        agent_id=agent_id,
        candidate_version='backend-delta-bad',
        physical_parameters=75_000_000,
        passed=True,
        false_accepts=1,
        regressions=0,
        evidence_ids=('EV-BAD',),
    )
    receipt = runtime.verification.evaluate_candidate(bad)
    assert receipt.accepted is False
    with pytest.raises(PermissionError):
        runtime.verification.promote_candidate(receipt.receipt_id)
    assert runtime.registry.get(agent_id).neural_version == original

    good = CandidateEvaluation(
        agent_id=agent_id,
        candidate_version='backend-delta-good',
        physical_parameters=76_000_000,
        passed=True,
        false_accepts=0,
        regressions=0,
        evidence_ids=('EV-GOOD-1', 'EV-GOOD-2'),
    )
    good_receipt = runtime.verification.evaluate_candidate(good)
    runtime.verification.promote_candidate(good_receipt.receipt_id)
    assert runtime.registry.get(agent_id).neural_version == 'backend-delta-good'

    rollback = runtime.verification.rollback(agent_id, reason='fresh external regression')
    assert rollback.restored_version == original
    assert runtime.registry.get(agent_id).neural_version == original


def test_neural_candidate_at_100m_is_rejected_before_promotion():
    runtime = OrganizationRuntime.first_generation()
    evaluation = CandidateEvaluation(
        agent_id='planning.chief',
        candidate_version='planner-too-large',
        physical_parameters=100_000_000,
        passed=True,
        false_accepts=0,
        regressions=0,
        evidence_ids=('EV-1',),
    )
    receipt = runtime.verification.evaluate_candidate(evaluation)
    assert receipt.accepted is False
    assert receipt.reason == 'parameter_ceiling_exceeded'
