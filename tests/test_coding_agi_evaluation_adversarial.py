import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord
from cogcoder.organization.evaluation_regimes import (
    BenchmarkDomain, BenchmarkRegimeRegistry, EvidenceProvenanceClass, EvaluationMode,
)
from cogcoder.organization.evaluation_evidence import EvaluationEvidenceLedger
from cogcoder.organization.evaluation_claims import ClaimBoundaryEngine, ClaimClass, ClaimDisposition
from cogcoder.organization.evaluation_stress import LongHorizonStressLedger
from cogcoder.organization.evaluation_parameters import ParameterScalingAuthority, ScalingDecision


def test_synthetic_evidence_cannot_be_laundered_into_external_independent_claim():
    runtime = OrganizationRuntime.first_generation()
    regimes = BenchmarkRegimeRegistry()
    regime = regimes.register(
        regime_id='synthetic', benchmark_id='synthetic-bench', domain=BenchmarkDomain.CODING,
        task_set_digest='tasks', repository_revision_digest='repo', tool_envelope_digest='tools',
        compute_budget_units=10, tool_call_budget=1, external_core_budget=1, wall_clock_budget_ms=1000,
        active_agent_budget=1, freshness_epoch=1, evaluator_protocol_version='p1',
        provenance_class=EvidenceProvenanceClass.INTERNAL_SYNTHETIC, fresh=True, heldout=False,
    )
    evidence = EvaluationEvidenceLedger(registry=runtime.registry, regimes=regimes)
    obs = evidence.record_observation(
        observation_id='synthetic-perfect', regime_id=regime.regime_id, mode=EvaluationMode.ORGANIZATION,
        producer_revision='system', score=1.0, task_count=100, pass_count=100, false_accepts=0,
        regressions=0, compute_units=10, tool_calls=1, external_core_calls=0, wall_clock_ms=100,
        energy_joules=1.0, active_agents=1, evidence_artifact_ids=('a',),
        evidence=EvidenceRecord('e', 'verification.chief', True), external_evaluator_id=None,
    )
    claims = ClaimBoundaryEngine(
        registry=runtime.registry, regimes=regimes, evidence=evidence,
        stress=LongHorizonStressLedger(registry=runtime.registry),
    )
    result = claims.assess('launder-attempt', ClaimClass.EXTERNAL_REPRODUCIBLE_CAPABILITY,
                           observation_ids=(obs.observation_id,), reproduction_receipt_id='fake-repro')
    assert result.disposition is ClaimDisposition.BLOCKED


def test_parameter_count_prestige_cannot_authorize_scaling_without_measured_gain():
    runtime = OrganizationRuntime.first_generation()
    regimes = BenchmarkRegimeRegistry()
    regime = regimes.register(
        regime_id='scale-adversarial', benchmark_id='scale', domain=BenchmarkDomain.CODING,
        task_set_digest='tasks', repository_revision_digest='repo', tool_envelope_digest='tools',
        compute_budget_units=100, tool_call_budget=10, external_core_budget=2, wall_clock_budget_ms=10000,
        active_agent_budget=1, freshness_epoch=1, evaluator_protocol_version='p1',
        provenance_class=EvidenceProvenanceClass.EXTERNAL_INDEPENDENT, fresh=True, heldout=True,
    )
    evidence = EvaluationEvidenceLedger(registry=runtime.registry, regimes=regimes)
    def obs(oid, score):
        return evidence.record_observation(
            observation_id=oid, regime_id=regime.regime_id, mode=EvaluationMode.SINGLE_AGENT,
            producer_revision=oid, score=score, task_count=100, pass_count=int(score * 100),
            false_accepts=0, regressions=0, compute_units=80, tool_calls=5, external_core_calls=1,
            wall_clock_ms=5000, energy_joules=100.0, active_agents=1, evidence_artifact_ids=(oid,),
            evidence=EvidenceRecord('ev-' + oid, 'verification.chief', True),
            external_evaluator_id='external-lab',
        )
    base = obs('base', 0.80)
    giant = obs('giant', 0.80)
    scaling = ParameterScalingAuthority(registry=runtime.registry, evidence=evidence)
    proposal = scaling.propose_scaling(
        proposal_id='prestige', agent_id='coding.backend.01', candidate_physical_parameters=900_000_000,
        baseline_observation_id=base.observation_id, candidate_observation_id=giant.observation_id,
        compute_cost_ratio=1.0, storage_delta_bytes=1_000_000_000, latency_delta_ms=100,
        energy_delta_joules=100.0, economic_capacity_digest='capacity',
        verifier_ids=('verification.chief', 'architecture.chief'), external_evaluator_id='external-lab',
        evidence_ids=('proof',),
    )
    assert scaling.decide_scaling(proposal.proposal_id).decision is ScalingDecision.REJECTED


def test_benchmark_regime_id_cannot_be_rebound_after_results_exist():
    registry = BenchmarkRegimeRegistry()
    registry.register(
        regime_id='immutable', benchmark_id='b', domain=BenchmarkDomain.DEBUGGING,
        task_set_digest='tasks1', repository_revision_digest='repo1', tool_envelope_digest='tools',
        compute_budget_units=10, tool_call_budget=1, external_core_budget=1, wall_clock_budget_ms=1000,
        active_agent_budget=1, freshness_epoch=1, evaluator_protocol_version='p1',
        provenance_class=EvidenceProvenanceClass.INTERNAL_REAL_REPOSITORY, fresh=True, heldout=True,
    )
    with pytest.raises(ValueError):
        registry.register(
            regime_id='immutable', benchmark_id='b', domain=BenchmarkDomain.DEBUGGING,
            task_set_digest='tasks2', repository_revision_digest='repo1', tool_envelope_digest='tools',
            compute_budget_units=10, tool_call_budget=1, external_core_budget=1, wall_clock_budget_ms=1000,
            active_agent_budget=1, freshness_epoch=1, evaluator_protocol_version='p1',
            provenance_class=EvidenceProvenanceClass.INTERNAL_REAL_REPOSITORY, fresh=True, heldout=True,
        )


@pytest.mark.parametrize('claim', [ClaimClass.AGI, ClaimClass.FRONTIER_EQUIVALENCE])
def test_no_authority_override_can_unlock_hard_disabled_claim_class(claim):
    runtime = OrganizationRuntime.first_generation()
    regimes = BenchmarkRegimeRegistry()
    evidence = EvaluationEvidenceLedger(registry=runtime.registry, regimes=regimes)
    claims = ClaimBoundaryEngine(
        registry=runtime.registry, regimes=regimes, evidence=evidence,
        stress=LongHorizonStressLedger(registry=runtime.registry),
    )
    result = claims.assess('hard-block-' + claim.value, claim, central_override_id='central-override-1')
    assert result.disposition is ClaimDisposition.BLOCKED
    assert result.override_effective is False
