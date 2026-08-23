from __future__ import annotations

import pytest

from cogcoder.organization.campaign import CampaignStatus, EvaluationCampaignControlPlane
from cogcoder.organization.campaign_contamination import CampaignContaminationLedger
from cogcoder.organization.campaign_ingest import CampaignIngestor
from cogcoder.organization.campaign_repository import RepositorySnapshotRegistry
from cogcoder.organization.campaign_runner import CampaignRunLedger
from cogcoder.organization.campaign_tasks import CampaignPartition, CampaignTaskRegistry
from cogcoder.organization.evaluation_regimes import BenchmarkDomain, EvidenceProvenanceClass, EvaluationMode
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord


def _fixture():
    runtime = OrganizationRuntime.first_generation()
    repos = RepositorySnapshotRegistry()
    repos.register(
        snapshot_id='repo-1', repository='example/project', revision='a' * 40,
        language='python', toolchain_digest='toolchain-v1', test_command_digest='pytest-v1',
        contamination_policy_digest='contam-v1', source_metadata={},
    )
    tasks = CampaignTaskRegistry(repositories=repos)
    for i in (1, 2):
        tasks.register(
            task_id=f'task-{i}', domain=BenchmarkDomain.CODING, repository_snapshot_id='repo-1',
            objective=f'Fix bug {i}', acceptance_command_digest=f'accept-{i}', difficulty='medium',
            allowed_tools=('pytest',), allowed_cores=('lsp',), compute_budget_units=100,
            tool_call_budget=20, external_core_budget=10, wall_clock_budget_ms=60_000,
            active_agent_budget=8, evaluator_protocol_version='campaign-eval-v1', contamination_tags=(),
        )
        tasks.assign_partition(f'task-{i}', CampaignPartition.HELDOUT)
    tasks.freeze_partitions()
    campaigns = EvaluationCampaignControlPlane(repositories=repos, tasks=tasks)
    campaigns.create_campaign(
        campaign_id='campaign-1', benchmark_id='real-repo-coding-v1', task_ids=('task-1', 'task-2'),
        modes=(EvaluationMode.ORGANIZATION,), freshness_epoch=1, runner_protocol_version='campaign-runner-v1',
    )
    campaigns.freeze('campaign-1'); campaigns.start('campaign-1')
    runs = CampaignRunLedger(campaigns=campaigns, tasks=tasks)
    contamination = CampaignContaminationLedger(tasks=tasks)
    return runtime, repos, tasks, campaigns, runs, contamination


def _record(runs: CampaignRunLedger, runtime: OrganizationRuntime, task_id: str, passed: bool, n: int):
    artifact = runtime.artifacts.put(
        kind='campaign-run-evidence', producer_agent_id='verification.integration-e2e.01',
        content=f'evidence-{task_id}-{passed}', evidence_refs=(), metadata={'task_id': task_id},
    )
    runs.create_spec(
        run_id=f'run-{n}', campaign_id='campaign-1', task_id=task_id, mode=EvaluationMode.ORGANIZATION,
        producer_revision='candidate-sha', environment_digest='env-v1', toolchain_digest='toolchain-v1',
    )
    return runs.record_result(
        run_id=f'run-{n}', passed=passed, false_accepts=0, regressions=0,
        compute_units=40, tool_calls=5, external_core_calls=2, wall_clock_ms=10_000,
        energy_joules=20.0, active_agents=4, output_artifact_ids=(artifact.artifact_id,),
        termination_reason='completed' if passed else 'test_failed',
    )


def test_ingestion_derives_score_and_resources_from_task_receipts():
    runtime, repos, tasks, campaigns, runs, contamination = _fixture()
    _record(runs, runtime, 'task-1', True, 1); _record(runs, runtime, 'task-2', False, 2)
    contamination.scan(
        campaign_id='campaign-1', task_ids=('task-1', 'task-2'), training_refs=(), distillation_refs=(), personal_skill_refs=(),
    )
    ingestor = CampaignIngestor(
        registry=runtime.registry, artifacts=runtime.artifacts, evaluation=runtime.evaluation_scaling,
        repositories=repos, tasks=tasks, campaigns=campaigns, runs=runs, contamination=contamination,
    )
    receipt = ingestor.ingest_mode(
        campaign_id='campaign-1', mode=EvaluationMode.ORGANIZATION,
        provenance_class=EvidenceProvenanceClass.INTERNAL_REAL_REPOSITORY,
        evidence=EvidenceRecord('campaign-evidence-1', 'verification.integration-e2e.01', True),
        external_evaluator_id=None,
    )
    observation = runtime.evaluation_scaling.evidence.get_observation(receipt.observation_id)
    assert observation.task_count == 2
    assert observation.pass_count == 1
    assert observation.score == 0.5
    assert observation.compute_units == 80
    assert observation.tool_calls == 10
    assert observation.external_core_calls == 4
    assert observation.wall_clock_ms == 20_000
    assert observation.energy_joules == 40.0
    assert observation.active_agents == 4
    assert campaigns.get('campaign-1').status is CampaignStatus.EVIDENCE_READY


def test_ingestion_rejects_incomplete_mode_and_missing_artifact():
    runtime, repos, tasks, campaigns, runs, contamination = _fixture()
    _record(runs, runtime, 'task-1', True, 1)
    contamination.scan(
        campaign_id='campaign-1', task_ids=('task-1', 'task-2'), training_refs=(), distillation_refs=(), personal_skill_refs=(),
    )
    ingestor = CampaignIngestor(
        registry=runtime.registry, artifacts=runtime.artifacts, evaluation=runtime.evaluation_scaling,
        repositories=repos, tasks=tasks, campaigns=campaigns, runs=runs, contamination=contamination,
    )
    with pytest.raises(PermissionError):
        ingestor.ingest_mode(
            campaign_id='campaign-1', mode=EvaluationMode.ORGANIZATION,
            provenance_class=EvidenceProvenanceClass.INTERNAL_REAL_REPOSITORY,
            evidence=EvidenceRecord('campaign-evidence-1', 'verification.integration-e2e.01', True),
            external_evaluator_id=None,
        )


def test_external_independent_evaluator_cannot_spoof_permanent_identity():
    runtime, repos, tasks, campaigns, runs, contamination = _fixture()
    _record(runs, runtime, 'task-1', True, 1); _record(runs, runtime, 'task-2', True, 2)
    contamination.scan(
        campaign_id='campaign-1', task_ids=('task-1', 'task-2'), training_refs=(), distillation_refs=(), personal_skill_refs=(),
    )
    ingestor = CampaignIngestor(
        registry=runtime.registry, artifacts=runtime.artifacts, evaluation=runtime.evaluation_scaling,
        repositories=repos, tasks=tasks, campaigns=campaigns, runs=runs, contamination=contamination,
    )
    with pytest.raises(PermissionError):
        ingestor.ingest_mode(
            campaign_id='campaign-1', mode=EvaluationMode.ORGANIZATION,
            provenance_class=EvidenceProvenanceClass.EXTERNAL_INDEPENDENT,
            evidence=EvidenceRecord('campaign-evidence-1', 'verification.integration-e2e.01', True),
            external_evaluator_id='verification.integration-e2e.01',
        )
