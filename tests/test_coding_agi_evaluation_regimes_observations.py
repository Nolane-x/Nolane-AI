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


def _regimes():
    return BenchmarkRegimeRegistry()


def _register(registry, *, regime_id='regime-1', provenance=EvidenceProvenanceClass.INTERNAL_REAL_REPOSITORY,
              fresh=True, heldout=True, task='tasks-a', repo='repo-a', tools='tools-a', compute=100):
    return registry.register(
        regime_id=regime_id,
        benchmark_id='real-repo-coding-v1',
        domain=BenchmarkDomain.CODING,
        task_set_digest=task,
        repository_revision_digest=repo,
        tool_envelope_digest=tools,
        compute_budget_units=compute,
        tool_call_budget=20,
        external_core_budget=8,
        wall_clock_budget_ms=60_000,
        active_agent_budget=8,
        freshness_epoch=42,
        evaluator_protocol_version='eval-protocol-1',
        provenance_class=provenance,
        fresh=fresh,
        heldout=heldout,
    )


def test_regime_is_immutable_and_explicit_about_provenance_freshness_and_budget():
    registry = _regimes()
    row = _register(registry)
    assert row.provenance_class is EvidenceProvenanceClass.INTERNAL_REAL_REPOSITORY
    assert row.fresh is True and row.heldout is True
    assert row.budget_digest
    assert registry.register(**row.registration_kwargs()) == row
    with pytest.raises(ValueError):
        _register(registry, repo='repo-b')


def test_regime_digest_changes_when_fairness_basis_changes():
    rows = []
    for idx, kwargs in enumerate((
        {'task': 'tasks-b'}, {'repo': 'repo-b'}, {'tools': 'tools-b'}, {'compute': 101},
    ), start=1):
        reg = _regimes()
        rows.append(_register(reg, regime_id=f'regime-{idx}', **kwargs).regime_digest)
    assert len(set(rows)) == len(rows)


def test_external_independent_observation_requires_non_organization_evaluator_and_clean_evidence():
    runtime = OrganizationRuntime.first_generation()
    regimes = _regimes()
    regime = _register(regimes, provenance=EvidenceProvenanceClass.EXTERNAL_INDEPENDENT)
    ledger = EvaluationEvidenceLedger(registry=runtime.registry, regimes=regimes)
    evidence = EvidenceRecord('eval-evidence-1', 'verification.chief', True)

    with pytest.raises(PermissionError):
        ledger.record_observation(
            observation_id='obs-bad', regime_id=regime.regime_id, mode=EvaluationMode.ORGANIZATION,
            producer_revision='system-r1', score=0.70, task_count=10, pass_count=7,
            false_accepts=0, regressions=0, compute_units=90, tool_calls=10,
            external_core_calls=2, wall_clock_ms=30_000, energy_joules=1000.0,
            active_agents=6, evidence_artifact_ids=('artifact-e1',), evidence=evidence,
            external_evaluator_id='verification.chief',
        )

    row = ledger.record_observation(
        observation_id='obs-good', regime_id=regime.regime_id, mode=EvaluationMode.ORGANIZATION,
        producer_revision='system-r1', score=0.70, task_count=10, pass_count=7,
        false_accepts=0, regressions=0, compute_units=90, tool_calls=10,
        external_core_calls=2, wall_clock_ms=30_000, energy_joules=1000.0,
        active_agents=6, evidence_artifact_ids=('artifact-e1',), evidence=evidence,
        external_evaluator_id='outside-lab-A',
    )
    assert row.external_evaluator_id == 'outside-lab-A'
    assert row.provenance_class is EvidenceProvenanceClass.EXTERNAL_INDEPENDENT


def test_internal_synthetic_observation_remains_labeled_internal():
    runtime = OrganizationRuntime.first_generation()
    regimes = _regimes()
    regime = _register(regimes, provenance=EvidenceProvenanceClass.INTERNAL_SYNTHETIC)
    ledger = EvaluationEvidenceLedger(registry=runtime.registry, regimes=regimes)
    row = ledger.record_observation(
        observation_id='obs-internal', regime_id=regime.regime_id, mode=EvaluationMode.SINGLE_AGENT,
        producer_revision='coding.backend.01@v1', score=1.0, task_count=1, pass_count=1,
        false_accepts=0, regressions=0, compute_units=10, tool_calls=1,
        external_core_calls=0, wall_clock_ms=100, energy_joules=None, active_agents=1,
        evidence_artifact_ids=('internal-artifact',),
        evidence=EvidenceRecord('internal-evidence', 'verification.chief', True),
        external_evaluator_id=None,
    )
    assert row.provenance_class is EvidenceProvenanceClass.INTERNAL_SYNTHETIC
    assert row.external_evaluator_id is None
