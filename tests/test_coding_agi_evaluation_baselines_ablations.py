import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord
from cogcoder.organization.evaluation_regimes import (
    BenchmarkDomain,
    BenchmarkRegimeRegistry,
    EvidenceProvenanceClass,
    EvaluationMode,
)
from cogcoder.organization.evaluation_evidence import EvaluationEvidenceLedger


def _setup():
    runtime = OrganizationRuntime.first_generation()
    regimes = BenchmarkRegimeRegistry()
    regime = regimes.register(
        regime_id='matched-1', benchmark_id='repo-suite', domain=BenchmarkDomain.CROSS_DOMAIN,
        task_set_digest='tasks', repository_revision_digest='repo', tool_envelope_digest='tools',
        compute_budget_units=100, tool_call_budget=20, external_core_budget=5,
        wall_clock_budget_ms=50_000, active_agent_budget=8, freshness_epoch=1,
        evaluator_protocol_version='p1', provenance_class=EvidenceProvenanceClass.EXTERNAL_REPRODUCED,
        fresh=True, heldout=True,
    )
    return runtime, regimes, regime, EvaluationEvidenceLedger(registry=runtime.registry, regimes=regimes)


def _obs(ledger, regime, oid, mode, score, *, false_accepts=0, regressions=0, compute=90):
    return ledger.record_observation(
        observation_id=oid, regime_id=regime.regime_id, mode=mode,
        producer_revision=f'{mode.value}@v1', score=score, task_count=20, pass_count=int(score * 20),
        false_accepts=false_accepts, regressions=regressions, compute_units=compute,
        tool_calls=10, external_core_calls=2, wall_clock_ms=20_000, energy_joules=100.0,
        active_agents=1 if mode is EvaluationMode.SINGLE_AGENT else 6,
        evidence_artifact_ids=(f'art-{oid}',),
        evidence=EvidenceRecord(f'ev-{oid}', 'verification.chief', True),
        external_evaluator_id=None,
    )


def test_organization_must_beat_single_agent_and_flat_swarm_under_same_regime():
    _, _, regime, ledger = _setup()
    org = _obs(ledger, regime, 'org', EvaluationMode.ORGANIZATION, 0.80)
    single = _obs(ledger, regime, 'single', EvaluationMode.SINGLE_AGENT, 0.65)
    swarm = _obs(ledger, regime, 'swarm', EvaluationMode.FLAT_SWARM, 0.70)
    c1 = ledger.compare_matched_budget(org.observation_id, single.observation_id)
    c2 = ledger.compare_matched_budget(org.observation_id, swarm.observation_id)
    assert c1.comparable and c1.improved
    assert c2.comparable and c2.improved
    assert ledger.organization_superiority(org.observation_id, (c1.comparison_id, c2.comparison_id)).supported


def test_score_gain_is_not_a_win_when_safety_gets_worse_or_budget_is_exceeded():
    _, _, regime, ledger = _setup()
    single = _obs(ledger, regime, 'single', EvaluationMode.SINGLE_AGENT, 0.60)
    unsafe = _obs(ledger, regime, 'unsafe', EvaluationMode.ORGANIZATION, 0.90, false_accepts=1)
    over = _obs(ledger, regime, 'over', EvaluationMode.ORGANIZATION, 0.90, compute=101)
    assert not ledger.compare_matched_budget(unsafe.observation_id, single.observation_id).improved
    assert not ledger.compare_matched_budget(over.observation_id, single.observation_id).improved


def test_different_regime_is_incomparable_not_an_improvement():
    runtime, regimes, regime, ledger = _setup()
    other = regimes.register(
        regime_id='matched-2', benchmark_id='repo-suite', domain=BenchmarkDomain.CROSS_DOMAIN,
        task_set_digest='tasks', repository_revision_digest='repo-CHANGED', tool_envelope_digest='tools',
        compute_budget_units=100, tool_call_budget=20, external_core_budget=5,
        wall_clock_budget_ms=50_000, active_agent_budget=8, freshness_epoch=1,
        evaluator_protocol_version='p1', provenance_class=EvidenceProvenanceClass.EXTERNAL_REPRODUCED,
        fresh=True, heldout=True,
    )
    org = _obs(ledger, regime, 'org', EvaluationMode.ORGANIZATION, 0.90)
    baseline = _obs(ledger, other, 'single-other', EvaluationMode.SINGLE_AGENT, 0.50)
    result = ledger.compare_matched_budget(org.observation_id, baseline.observation_id)
    assert not result.comparable
    assert not result.improved
    assert result.reason == 'regime_mismatch'


@pytest.mark.parametrize('mode', [
    EvaluationMode.ORGANIZATION_NO_MEMORY,
    EvaluationMode.ORGANIZATION_NO_TOOLS,
    EvaluationMode.ORGANIZATION_NO_SPECIALIZATION,
    EvaluationMode.ORGANIZATION_NO_COORDINATION,
])
def test_ablations_report_component_delta_without_changing_regime(mode):
    _, _, regime, ledger = _setup()
    full = _obs(ledger, regime, 'full-' + mode.value, EvaluationMode.ORGANIZATION, 0.82)
    ablated = _obs(ledger, regime, 'ablated-' + mode.value, mode, 0.68)
    assessment = ledger.assess_ablation(full.observation_id, ablated.observation_id)
    assert assessment.comparable
    assert assessment.score_delta == pytest.approx(0.14)
    assert assessment.ablation_mode is mode
