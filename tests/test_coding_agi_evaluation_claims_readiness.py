import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord
from cogcoder.organization.evaluation_regimes import (
    BenchmarkDomain, BenchmarkRegimeRegistry, EvidenceProvenanceClass, EvaluationMode,
)
from cogcoder.organization.evaluation_evidence import EvaluationEvidenceLedger
from cogcoder.organization.evaluation_stress import LongHorizonStressLedger, StressScenarioKind
from cogcoder.organization.evaluation_claims import ClaimBoundaryEngine, ClaimClass, ClaimDisposition


def _base():
    runtime = OrganizationRuntime.first_generation()
    regimes = BenchmarkRegimeRegistry()
    evidence = EvaluationEvidenceLedger(registry=runtime.registry, regimes=regimes)
    stress = LongHorizonStressLedger(registry=runtime.registry)
    engine = ClaimBoundaryEngine(registry=runtime.registry, regimes=regimes, evidence=evidence, stress=stress)
    return runtime, regimes, evidence, stress, engine


def _regime(regimes, rid, domain, *, heldout=True, provenance=EvidenceProvenanceClass.EXTERNAL_INDEPENDENT):
    return regimes.register(
        regime_id=rid, benchmark_id='bench-' + rid, domain=domain,
        task_set_digest='tasks-' + rid, repository_revision_digest='repo-' + rid,
        tool_envelope_digest='tools', compute_budget_units=100, tool_call_budget=20,
        external_core_budget=5, wall_clock_budget_ms=40_000, active_agent_budget=8,
        freshness_epoch=1, evaluator_protocol_version='p1', provenance_class=provenance,
        fresh=True, heldout=heldout,
    )


def _obs(evidence, regime, oid, mode, score, *, external='outside-evaluator'):
    return evidence.record_observation(
        observation_id=oid, regime_id=regime.regime_id, mode=mode,
        producer_revision='system-v1', score=score, task_count=10, pass_count=int(score * 10),
        false_accepts=0, regressions=0, compute_units=80, tool_calls=5, external_core_calls=1,
        wall_clock_ms=10_000, energy_joules=100.0, active_agents=1 if mode is EvaluationMode.SINGLE_AGENT else 6,
        evidence_artifact_ids=(f'art-{oid}',), evidence=EvidenceRecord(f'ev-{oid}', 'verification.chief', True),
        external_evaluator_id=external,
    )


def test_internal_synthetic_progress_stays_limited_to_internal_claim():
    _, regimes, evidence, stress, engine = _base()
    regime = _regime(regimes, 'internal', BenchmarkDomain.CODING, provenance=EvidenceProvenanceClass.INTERNAL_SYNTHETIC)
    obs = _obs(evidence, regime, 'internal-obs', EvaluationMode.ORGANIZATION, 1.0, external=None)
    internal = engine.assess('claim-internal', ClaimClass.INTERNAL_ENGINEERING_PROGRESS, observation_ids=(obs.observation_id,))
    external = engine.assess('claim-external', ClaimClass.EXTERNAL_REPRODUCIBLE_CAPABILITY, observation_ids=(obs.observation_id,))
    assert internal.disposition in (ClaimDisposition.SUPPORTED, ClaimDisposition.LIMITED)
    assert external.disposition is ClaimDisposition.BLOCKED


def test_organization_superiority_requires_both_single_agent_and_flat_swarm_wins():
    _, regimes, evidence, stress, engine = _base()
    regime = _regime(regimes, 'superiority', BenchmarkDomain.CROSS_DOMAIN)
    org = _obs(evidence, regime, 'org', EvaluationMode.ORGANIZATION, 0.85)
    single = _obs(evidence, regime, 'single', EvaluationMode.SINGLE_AGENT, 0.65)
    swarm = _obs(evidence, regime, 'swarm', EvaluationMode.FLAT_SWARM, 0.70)
    c_single = evidence.compare_matched_budget(org.observation_id, single.observation_id)
    c_swarm = evidence.compare_matched_budget(org.observation_id, swarm.observation_id)
    incomplete = engine.assess(
        'claim-superiority-incomplete', ClaimClass.ORGANIZATION_MATCHED_BUDGET_SUPERIORITY,
        comparison_ids=(c_single.comparison_id,),
    )
    complete = engine.assess(
        'claim-superiority-complete', ClaimClass.ORGANIZATION_MATCHED_BUDGET_SUPERIORITY,
        comparison_ids=(c_single.comparison_id, c_swarm.comparison_id),
    )
    assert incomplete.disposition is ClaimDisposition.BLOCKED
    assert complete.disposition is ClaimDisposition.SUPPORTED


def test_cross_domain_transfer_requires_three_domains_and_heldout_cross_domain_regime():
    _, regimes, evidence, stress, engine = _base()
    observations = []
    for idx, domain in enumerate((BenchmarkDomain.CODING, BenchmarkDomain.DEBUGGING, BenchmarkDomain.RESEARCH), start=1):
        r = _regime(regimes, f'domain-{idx}', domain)
        observations.append(_obs(evidence, r, f'obs-{idx}', EvaluationMode.ORGANIZATION, 0.8).observation_id)
    without_cross = engine.assess('cross-no-heldout', ClaimClass.CROSS_DOMAIN_TRANSFER, observation_ids=tuple(observations))
    cross = _regime(regimes, 'heldout-cross', BenchmarkDomain.CROSS_DOMAIN, heldout=True)
    observations.append(_obs(evidence, cross, 'obs-cross', EvaluationMode.ORGANIZATION, 0.78).observation_id)
    with_cross = engine.assess('cross-good', ClaimClass.CROSS_DOMAIN_TRANSFER, observation_ids=tuple(observations))
    assert without_cross.disposition is ClaimDisposition.BLOCKED
    assert with_cross.disposition is ClaimDisposition.SUPPORTED


@pytest.mark.parametrize('claim_class', [ClaimClass.AGI, ClaimClass.FRONTIER_EQUIVALENCE])
def test_unrestricted_claims_are_hard_blocked_even_with_override_or_perfect_score(claim_class):
    runtime, regimes, evidence, stress, engine = _base()
    regime = _regime(regimes, 'perfect', BenchmarkDomain.CROSS_DOMAIN)
    obs = _obs(evidence, regime, 'perfect-obs', EvaluationMode.ORGANIZATION, 1.0)
    assessment = engine.assess(
        'forbidden-' + claim_class.value, claim_class, observation_ids=(obs.observation_id,),
        central_override_id='override-does-not-matter',
    )
    assert assessment.disposition is ClaimDisposition.BLOCKED
    assert 'hard_disabled_claim_class' in assessment.reasons


def test_readiness_report_is_separable_and_does_not_emit_single_agi_score():
    _, regimes, evidence, stress, engine = _base()
    report = engine.readiness(claim_assessment_ids=())
    state = report.to_state()
    assert 'agi_score' not in state
    assert set(state['gates']) >= {
        'benchmark_coverage', 'matched_budget_superiority', 'ablation_coverage',
        'long_horizon_reliability', 'external_reproducibility', 'parameter_accounting_completeness',
        'safety_cleanliness', 'scaling_evidence_completeness',
    }
