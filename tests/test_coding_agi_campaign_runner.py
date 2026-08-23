from __future__ import annotations

import pytest

from cogcoder.organization.campaign import EvaluationCampaignControlPlane
from cogcoder.organization.campaign_repository import RepositorySnapshotRegistry
from cogcoder.organization.campaign_runner import CampaignRunLedger
from cogcoder.organization.campaign_tasks import CampaignPartition, CampaignTaskRegistry
from cogcoder.organization.evaluation_regimes import BenchmarkDomain, EvaluationMode


def _fixture():
    repos = RepositorySnapshotRegistry()
    repos.register(
        snapshot_id='repo-1', repository='example/project', revision='a' * 40,
        language='python', toolchain_digest='toolchain-v1', test_command_digest='pytest-v1',
        contamination_policy_digest='contam-v1', source_metadata={},
    )
    tasks = CampaignTaskRegistry(repositories=repos)
    tasks.register(
        task_id='task-1', domain=BenchmarkDomain.CODING, repository_snapshot_id='repo-1',
        objective='Fix bug', acceptance_command_digest='accept-v1', difficulty='medium',
        allowed_tools=('pytest',), allowed_cores=('lsp',), compute_budget_units=100,
        tool_call_budget=20, external_core_budget=10, wall_clock_budget_ms=60_000,
        active_agent_budget=8, evaluator_protocol_version='campaign-eval-v1', contamination_tags=(),
    )
    tasks.assign_partition('task-1', CampaignPartition.HELDOUT); tasks.freeze_partitions()
    campaigns = EvaluationCampaignControlPlane(repositories=repos, tasks=tasks)
    campaigns.create_campaign(
        campaign_id='campaign-1', benchmark_id='real-repo-coding-v1', task_ids=('task-1',),
        modes=(EvaluationMode.SINGLE_AGENT, EvaluationMode.ORGANIZATION), freshness_epoch=1,
        runner_protocol_version='campaign-runner-v1',
    )
    campaigns.freeze('campaign-1'); campaigns.start('campaign-1')
    return repos, tasks, campaigns


def test_run_receipt_is_task_level_and_caller_cannot_inject_score():
    _, tasks, campaigns = _fixture()
    runs = CampaignRunLedger(campaigns=campaigns, tasks=tasks)
    spec = runs.create_spec(
        run_id='run-1', campaign_id='campaign-1', task_id='task-1',
        mode=EvaluationMode.ORGANIZATION, producer_revision='revision-1',
        environment_digest='env-v1', toolchain_digest='toolchain-v1',
    )
    with pytest.raises(TypeError):
        runs.record_result(
            run_id=spec.run_id, passed=True, false_accepts=0, regressions=0,
            compute_units=80, tool_calls=10, external_core_calls=4, wall_clock_ms=30_000,
            energy_joules=100.0, active_agents=4, output_artifact_ids=('artifact-1',),
            termination_reason='completed', score=1.0,
        )
    receipt = runs.record_result(
        run_id=spec.run_id, passed=True, false_accepts=0, regressions=0,
        compute_units=80, tool_calls=10, external_core_calls=4, wall_clock_ms=30_000,
        energy_joules=100.0, active_agents=4, output_artifact_ids=('artifact-1',),
        termination_reason='completed',
    )
    assert receipt.passed is True
    assert not hasattr(receipt, 'score')
    assert receipt.digest


def test_run_id_cannot_be_rebound_to_different_mode_or_output():
    _, tasks, campaigns = _fixture()
    runs = CampaignRunLedger(campaigns=campaigns, tasks=tasks)
    runs.create_spec(
        run_id='run-1', campaign_id='campaign-1', task_id='task-1', mode=EvaluationMode.ORGANIZATION,
        producer_revision='revision-1', environment_digest='env-v1', toolchain_digest='toolchain-v1',
    )
    with pytest.raises(ValueError):
        runs.create_spec(
            run_id='run-1', campaign_id='campaign-1', task_id='task-1', mode=EvaluationMode.SINGLE_AGENT,
            producer_revision='revision-1', environment_digest='env-v1', toolchain_digest='toolchain-v1',
        )
    runs.record_result(
        run_id='run-1', passed=False, false_accepts=0, regressions=0,
        compute_units=70, tool_calls=8, external_core_calls=3, wall_clock_ms=25_000,
        energy_joules=None, active_agents=3, output_artifact_ids=('artifact-a',), termination_reason='test_failed',
    )
    with pytest.raises(ValueError):
        runs.record_result(
            run_id='run-1', passed=True, false_accepts=0, regressions=0,
            compute_units=70, tool_calls=8, external_core_calls=3, wall_clock_ms=25_000,
            energy_joules=None, active_agents=3, output_artifact_ids=('artifact-b',), termination_reason='completed',
        )


def test_mode_must_be_declared_by_frozen_campaign():
    _, tasks, campaigns = _fixture()
    runs = CampaignRunLedger(campaigns=campaigns, tasks=tasks)
    with pytest.raises(PermissionError):
        runs.create_spec(
            run_id='run-ablation', campaign_id='campaign-1', task_id='task-1',
            mode=EvaluationMode.ORGANIZATION_NO_MEMORY, producer_revision='revision-1',
            environment_digest='env-v1', toolchain_digest='toolchain-v1',
        )
