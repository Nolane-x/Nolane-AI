import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord


def _obs(runtime, *, observation_id, score, regime='repo-v1', regressions=0, verifier='verification.integration-e2e.01'):
    return runtime.individual_evolution.record_benchmark_observation(
        observation_id=observation_id, agent_id='coding.backend.01',
        benchmark_id='backend-repair-heldout', regime_digest=regime,
        score=score, regressions=regressions,
        evidence=EvidenceRecord('EV-' + observation_id, verifier, True),
    )


def test_longitudinal_improvement_requires_same_regime_higher_score_no_regressions_and_external_evidence():
    runtime = OrganizationRuntime.first_generation()
    baseline = _obs(runtime, observation_id='BASE', score=0.50)
    candidate = _obs(runtime, observation_id='CAND', score=0.66)
    assessment = runtime.individual_evolution.assess_longitudinal_improvement(
        agent_id='coding.backend.01', baseline_observation_id=baseline.observation_id,
        candidate_observation_id=candidate.observation_id,
    )
    assert assessment.improved is True
    assert assessment.score_delta == pytest.approx(0.16)

    changed_regime = _obs(runtime, observation_id='REGIME', score=0.90, regime='repo-v2')
    mismatch = runtime.individual_evolution.assess_longitudinal_improvement(
        agent_id='coding.backend.01', baseline_observation_id=baseline.observation_id,
        candidate_observation_id=changed_regime.observation_id,
    )
    assert mismatch.improved is False
    assert mismatch.reason == 'benchmark_regime_mismatch'

    regressed = _obs(runtime, observation_id='REGRESSED', score=0.75, regressions=1)
    rejected = runtime.individual_evolution.assess_longitudinal_improvement(
        agent_id='coding.backend.01', baseline_observation_id=baseline.observation_id,
        candidate_observation_id=regressed.observation_id,
    )
    assert rejected.improved is False
    assert rejected.reason == 'candidate_regressions_detected'


def test_agent_cannot_self_certify_longitudinal_benchmark_improvement():
    runtime = OrganizationRuntime.first_generation()
    with pytest.raises(PermissionError):
        runtime.individual_evolution.record_benchmark_observation(
            observation_id='SELF', agent_id='coding.backend.01',
            benchmark_id='backend-repair-heldout', regime_digest='repo-v1', score=0.99,
            regressions=0, evidence=EvidenceRecord('EV-SELF-BENCH', 'coding.backend.01', True),
        )
