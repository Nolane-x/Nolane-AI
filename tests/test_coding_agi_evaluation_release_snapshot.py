import copy
import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord
from cogcoder.organization.evaluation_regimes import BenchmarkDomain, EvidenceProvenanceClass, EvaluationMode


def _populate(runtime):
    control = runtime.evaluation_scaling
    regime = control.regimes.register(
        regime_id='release-regime', benchmark_id='release-bench', domain=BenchmarkDomain.CODING,
        task_set_digest='release-tasks', repository_revision_digest='repo-sha', tool_envelope_digest='tools',
        compute_budget_units=100, tool_call_budget=10, external_core_budget=2,
        wall_clock_budget_ms=10_000, active_agent_budget=4, freshness_epoch=5,
        evaluator_protocol_version='protocol-v1', provenance_class=EvidenceProvenanceClass.EXTERNAL_INDEPENDENT,
        fresh=True, heldout=True,
    )
    obs = control.evidence.record_observation(
        observation_id='release-obs', regime_id=regime.regime_id, mode=EvaluationMode.ORGANIZATION,
        producer_revision='system-v1', score=0.8, task_count=10, pass_count=8,
        false_accepts=0, regressions=0, compute_units=90, tool_calls=5, external_core_calls=1,
        wall_clock_ms=5000, energy_joules=200.0, active_agents=4,
        evidence_artifact_ids=('external-evidence-artifact',),
        evidence=EvidenceRecord('release-evidence', 'verification.chief', True),
        external_evaluator_id='independent-lab-release',
    )
    report = control.parameters.parameter_footprint(
        active_agent_ids=('nolane.central', 'verification.chief'), active_ephemeral_count=0,
        compute_units=90, latency_ms=5000, energy_joules=200.0,
    )
    artifact = runtime.artifacts.put(
        kind='evaluation-release-bundle', producer_agent_id='verification.chief',
        content='immutable evaluation bundle', evidence_refs=('release-evidence',),
        metadata={'regime': regime.regime_digest},
    )
    return regime, obs, report, artifact


def test_release_requires_independent_reproduction_before_external_reproducible_status():
    runtime = OrganizationRuntime.first_generation()
    regime, obs, report, artifact = _populate(runtime)
    release = runtime.evaluation_scaling.releases.create_release(
        release_id='eval-release-1', release_version='1.0.0', source_commit_sha='a' * 40,
        regime_ids=(regime.regime_id,), observation_ids=(obs.observation_id,), comparison_ids=(),
        stress_assessment_ids=(), parameter_report_id=report.report_id, claim_assessment_ids=(),
        scaling_decision_ids=(), artifact_ids=(artifact.artifact_id,),
        evaluator_protocol_version='protocol-v1', independent_evaluator_ids=('independent-lab-release',),
        reproduction_command_digest='cmd-digest', environment_toolchain_digest='env-digest', created_logical_epoch=10,
    )
    assert not runtime.evaluation_scaling.releases.is_externally_reproducible(release.release_id)
    reproduction = runtime.evaluation_scaling.releases.record_reproduction(
        release_id=release.release_id, evaluator_id='independent-lab-B',
        release_digest=release.digest, artifact_digest=artifact.digest,
        evaluator_protocol_version='protocol-v1', reproduction_command_digest='cmd-digest',
        environment_toolchain_digest='env-digest', passed=True,
    )
    assert reproduction.independent
    assert runtime.evaluation_scaling.releases.is_externally_reproducible(release.release_id)


def test_organization_runtime_snapshot_round_trip_preserves_evaluation_state_exactly():
    runtime = OrganizationRuntime.first_generation()
    _populate(runtime)
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(copy.deepcopy(state))
    assert restored.to_state() == state


def test_pre_part15_snapshot_restores_empty_evaluation_layer():
    runtime = OrganizationRuntime.first_generation()
    state = runtime.to_state()
    state.pop('evaluation_scaling')
    restored = OrganizationRuntime.from_state(state)
    assert restored.evaluation_scaling.is_empty()


def test_corrupt_evaluation_digest_fails_closed_on_restore():
    runtime = OrganizationRuntime.first_generation()
    _populate(runtime)
    state = runtime.to_state()
    rows = state['evaluation_scaling']['regimes']['regimes']
    assert rows
    rows[0]['regime_digest'] = '0' * 64
    with pytest.raises(ValueError):
        OrganizationRuntime.from_state(state)
