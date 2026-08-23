import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord
from cogcoder.organization.evaluation_regimes import (
    BenchmarkDomain, BenchmarkRegimeRegistry, EvidenceProvenanceClass, EvaluationMode,
)
from cogcoder.organization.evaluation_evidence import EvaluationEvidenceLedger
from cogcoder.organization.evaluation_parameters import ParameterScalingAuthority, ScalingDecision


def _setup():
    runtime = OrganizationRuntime.first_generation()
    regimes = BenchmarkRegimeRegistry()
    regime = regimes.register(
        regime_id='scale-regime', benchmark_id='scale-suite', domain=BenchmarkDomain.CODING,
        task_set_digest='heldout-tasks', repository_revision_digest='repo-rev', tool_envelope_digest='tool-env',
        compute_budget_units=100, tool_call_budget=10, external_core_budget=3,
        wall_clock_budget_ms=20_000, active_agent_budget=2, freshness_epoch=10,
        evaluator_protocol_version='p1', provenance_class=EvidenceProvenanceClass.EXTERNAL_INDEPENDENT,
        fresh=True, heldout=True,
    )
    ledger = EvaluationEvidenceLedger(registry=runtime.registry, regimes=regimes)
    return runtime, regimes, regime, ledger


def _obs(ledger, regime, oid, score, revision):
    return ledger.record_observation(
        observation_id=oid, regime_id=regime.regime_id, mode=EvaluationMode.SINGLE_AGENT,
        producer_revision=revision, score=score, task_count=100, pass_count=int(score * 100),
        false_accepts=0, regressions=0, compute_units=80, tool_calls=5,
        external_core_calls=1, wall_clock_ms=10_000, energy_joules=500.0, active_agents=1,
        evidence_artifact_ids=(f'art-{oid}',),
        evidence=EvidenceRecord(f'ev-{oid}', 'verification.chief', True),
        external_evaluator_id='external-lab-scale',
    )


def test_parameter_footprint_counts_shared_storage_once_and_labels_logical_view_separately():
    runtime, _, _, ledger = _setup()
    authority = ParameterScalingAuthority(registry=runtime.registry, evidence=ledger)
    report = authority.parameter_footprint(
        active_agent_ids=('nolane.central', 'coding.backend.01'),
        active_ephemeral_count=0, compute_units=123, latency_ms=456, energy_joules=789.0,
    )
    central = runtime.registry.get('nolane.central').parameter_accounting
    backend = runtime.registry.get('coding.backend.01').parameter_accounting
    assert report.shared_physical_parameters == 56_000_000
    assert report.local_physical_parameters == central.local_physical_parameters + backend.local_physical_parameters
    assert report.unique_stored_physical_parameters == report.shared_physical_parameters + report.local_physical_parameters
    assert report.logical_deployed_parameter_footprint == central.total_physical_parameters + backend.total_physical_parameters
    assert report.logical_deployed_parameter_footprint > report.unique_stored_physical_parameters


def test_future_over_100m_authorization_never_mutates_current_registry_or_parameter_accounting():
    runtime, _, regime, ledger = _setup()
    baseline = _obs(ledger, regime, 'baseline-scale', 0.70, 'candidate-agent-v1')
    candidate = _obs(ledger, regime, 'candidate-scale', 0.75, 'candidate-agent-v2')
    authority = ParameterScalingAuthority(registry=runtime.registry, evidence=ledger)
    before = runtime.registry.get('coding.backend.01')
    proposal = authority.propose_scaling(
        proposal_id='scale-proposal-1', agent_id='coding.backend.01', candidate_physical_parameters=120_000_000,
        baseline_observation_id=baseline.observation_id, candidate_observation_id=candidate.observation_id,
        compute_cost_ratio=1.50, storage_delta_bytes=250_000_000, latency_delta_ms=80,
        energy_delta_joules=100.0, economic_capacity_digest='capacity-2026q3',
        verifier_ids=('verification.chief', 'architecture.chief'),
        external_evaluator_id='external-lab-scale', evidence_ids=('budget-proof', 'capacity-proof'),
    )
    decision = authority.decide_scaling(proposal.proposal_id)
    after = runtime.registry.get('coding.backend.01')
    assert decision.decision is ScalingDecision.AUTHORIZED_FOR_FUTURE_EXPERIMENT
    assert before.neural_version == after.neural_version
    assert before.parameter_accounting == after.parameter_accounting
    assert after.parameter_accounting.total_physical_parameters < 100_000_000


def test_scaling_is_rejected_for_prestige_only_or_dirty_or_inefficient_gain():
    runtime, _, regime, ledger = _setup()
    baseline = _obs(ledger, regime, 'base', 0.70, 'v1')
    weak = _obs(ledger, regime, 'weak', 0.71, 'v2')
    authority = ParameterScalingAuthority(registry=runtime.registry, evidence=ledger)
    proposal = authority.propose_scaling(
        proposal_id='weak-proposal', agent_id='coding.backend.01', candidate_physical_parameters=150_000_000,
        baseline_observation_id=baseline.observation_id, candidate_observation_id=weak.observation_id,
        compute_cost_ratio=2.2, storage_delta_bytes=1, latency_delta_ms=1, energy_delta_joules=1.0,
        economic_capacity_digest='capacity', verifier_ids=('verification.chief', 'architecture.chief'),
        external_evaluator_id='external-lab-scale', evidence_ids=('e1',),
    )
    decision = authority.decide_scaling(proposal.proposal_id)
    assert decision.decision is ScalingDecision.REJECTED
    assert 'insufficient_marginal_gain' in decision.reasons
    assert 'efficiency_ratio_exceeded' in decision.reasons


def test_scaling_requires_cross_region_verifiers_external_evaluator_and_complete_cost_accounting():
    runtime, _, regime, ledger = _setup()
    baseline = _obs(ledger, regime, 'base2', 0.60, 'v1')
    candidate = _obs(ledger, regime, 'candidate2', 0.70, 'v2')
    authority = ParameterScalingAuthority(registry=runtime.registry, evidence=ledger)
    proposal = authority.propose_scaling(
        proposal_id='bad-verifiers', agent_id='coding.backend.01', candidate_physical_parameters=120_000_000,
        baseline_observation_id=baseline.observation_id, candidate_observation_id=candidate.observation_id,
        compute_cost_ratio=1.1, storage_delta_bytes=10, latency_delta_ms=10, energy_delta_joules=10.0,
        economic_capacity_digest='capacity', verifier_ids=('coding.chief', 'coding.core-algorithm.01'),
        external_evaluator_id='verification.chief', evidence_ids=('e1',),
    )
    decision = authority.decide_scaling(proposal.proposal_id)
    assert decision.decision is ScalingDecision.REJECTED
    assert 'insufficient_cross_region_verifiers' in decision.reasons
    assert 'external_evaluator_not_independent' in decision.reasons
