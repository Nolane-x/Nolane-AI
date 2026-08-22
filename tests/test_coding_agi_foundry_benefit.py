from cogcoder.organization.foundry_evidence import BenefitMode
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord


def _record(runtime, *, oid, mode, score, regime='regime-A', budget='budget-A', used=40, false_accepts=0, regressions=0, team_id=None):
    return runtime.foundry.record_benefit_observation(
        observation_id=oid, mode=mode, task_id='T-HARD', benchmark_id='hard-debug-v1',
        regime_digest=regime, budget_digest=budget, budget_limit_units=50,
        resource_units=used, score=score, false_accepts=false_accepts, regressions=regressions,
        team_id=team_id,
        evidence=EvidenceRecord(oid + '-EV', 'verification.spec-acceptance.01', True),
    )


def test_matched_budget_team_can_claim_benefit_only_with_higher_clean_score():
    runtime = OrganizationRuntime.first_generation()
    baseline = _record(runtime, oid='BASE', mode=BenefitMode.BASELINE, score=0.60, used=45)
    team = _record(runtime, oid='TEAM', mode=BenefitMode.EPHEMERAL_TEAM, score=0.76, used=49, team_id='team-hard')
    assessment = runtime.foundry.assess_benefit(baseline.observation_id, team.observation_id)
    assert assessment.improved
    assert assessment.score_delta == 0.16
    assert assessment.reason == 'matched_budget_improvement'


def test_different_regime_or_budget_is_incomparable_not_an_improvement():
    runtime = OrganizationRuntime.first_generation()
    baseline = _record(runtime, oid='BASE-A', mode=BenefitMode.BASELINE, score=0.60)
    other_regime = _record(
        runtime, oid='TEAM-B', mode=BenefitMode.EPHEMERAL_TEAM, score=0.90,
        regime='regime-B', team_id='team-b',
    )
    result = runtime.foundry.assess_benefit(baseline.observation_id, other_regime.observation_id)
    assert not result.improved
    assert result.reason == 'incomparable_regime'

    other_budget = _record(
        runtime, oid='TEAM-C', mode=BenefitMode.EPHEMERAL_TEAM, score=0.90,
        budget='budget-C', team_id='team-c',
    )
    result = runtime.foundry.assess_benefit(baseline.observation_id, other_budget.observation_id)
    assert not result.improved
    assert result.reason == 'incomparable_budget'


def test_over_budget_or_worse_false_accepts_regressions_cannot_claim_benefit():
    runtime = OrganizationRuntime.first_generation()
    baseline = _record(runtime, oid='BASE-D', mode=BenefitMode.BASELINE, score=0.60, used=45)
    over = _record(
        runtime, oid='TEAM-OVER', mode=BenefitMode.EPHEMERAL_TEAM, score=0.95,
        used=51, team_id='team-over',
    )
    result = runtime.foundry.assess_benefit(baseline.observation_id, over.observation_id)
    assert not result.improved
    assert result.reason == 'team_over_budget'

    worse = _record(
        runtime, oid='TEAM-WORSE', mode=BenefitMode.EPHEMERAL_TEAM, score=0.80,
        used=48, false_accepts=1, regressions=1, team_id='team-worse',
    )
    result = runtime.foundry.assess_benefit(baseline.observation_id, worse.observation_id)
    assert not result.improved
    assert result.reason == 'safety_regression'


def test_lower_or_equal_score_is_not_improvement_even_under_matched_budget():
    runtime = OrganizationRuntime.first_generation()
    baseline = _record(runtime, oid='BASE-E', mode=BenefitMode.BASELINE, score=0.70)
    team = _record(runtime, oid='TEAM-E', mode=BenefitMode.EPHEMERAL_TEAM, score=0.70, team_id='team-e')
    result = runtime.foundry.assess_benefit(baseline.observation_id, team.observation_id)
    assert not result.improved
    assert result.reason == 'no_score_improvement'
