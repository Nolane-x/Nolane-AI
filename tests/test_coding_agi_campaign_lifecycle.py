from __future__ import annotations

import pytest

from cogcoder.organization.campaign import CampaignStatus, EvaluationCampaignControlPlane
from cogcoder.organization.campaign_repository import RepositorySnapshotRegistry
from cogcoder.organization.campaign_tasks import CampaignPartition, CampaignTaskRegistry
from cogcoder.organization.evaluation_regimes import BenchmarkDomain, EvaluationMode


def _fixture():
    repos = RepositorySnapshotRegistry()
    repos.register(
        snapshot_id='repo-1', repository='example/project', revision='a' * 40,
        language='python', toolchain_digest='toolchain-v1', test_command_digest='pytest-digest',
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
    tasks.assign_partition('task-1', CampaignPartition.HELDOUT)
    tasks.freeze_partitions()
    return repos, tasks


def test_campaign_freeze_is_content_addressed_and_inputs_become_immutable():
    repos, tasks = _fixture()
    campaigns = EvaluationCampaignControlPlane(repositories=repos, tasks=tasks)
    row = campaigns.create_campaign(
        campaign_id='campaign-1', benchmark_id='real-repo-coding-v1', task_ids=('task-1',),
        modes=(EvaluationMode.SINGLE_AGENT, EvaluationMode.FLAT_SWARM, EvaluationMode.ORGANIZATION),
        freshness_epoch=1, runner_protocol_version='campaign-runner-v1',
    )
    assert row.status is CampaignStatus.DRAFT
    frozen = campaigns.freeze('campaign-1')
    assert frozen.status is CampaignStatus.FROZEN
    assert frozen.freeze_digest
    with pytest.raises(PermissionError):
        campaigns.replace_modes('campaign-1', (EvaluationMode.ORGANIZATION,))
    with pytest.raises(ValueError):
        campaigns.create_campaign(
            campaign_id='campaign-1', benchmark_id='different', task_ids=('task-1',),
            modes=(EvaluationMode.ORGANIZATION,), freshness_epoch=1,
            runner_protocol_version='campaign-runner-v1',
        )


def test_campaign_lifecycle_is_forward_only_and_terminal_states_do_not_reactivate():
    repos, tasks = _fixture()
    campaigns = EvaluationCampaignControlPlane(repositories=repos, tasks=tasks)
    campaigns.create_campaign(
        campaign_id='campaign-1', benchmark_id='real-repo-coding-v1', task_ids=('task-1',),
        modes=(EvaluationMode.ORGANIZATION,), freshness_epoch=1,
        runner_protocol_version='campaign-runner-v1',
    )
    campaigns.freeze('campaign-1')
    campaigns.start('campaign-1')
    assert campaigns.get('campaign-1').status is CampaignStatus.RUNNING
    campaigns.quarantine('campaign-1', reason='heldout_contamination')
    assert campaigns.get('campaign-1').status is CampaignStatus.QUARANTINED
    with pytest.raises(PermissionError):
        campaigns.start('campaign-1')


def test_campaign_snapshot_restores_status_and_freeze_digest_exactly():
    repos, tasks = _fixture()
    campaigns = EvaluationCampaignControlPlane(repositories=repos, tasks=tasks)
    campaigns.create_campaign(
        campaign_id='campaign-1', benchmark_id='real-repo-coding-v1', task_ids=('task-1',),
        modes=(EvaluationMode.ORGANIZATION,), freshness_epoch=1,
        runner_protocol_version='campaign-runner-v1',
    )
    frozen = campaigns.freeze('campaign-1')
    restored = EvaluationCampaignControlPlane.from_state(repositories=repos, tasks=tasks, state=campaigns.to_state())
    assert restored.get('campaign-1') == frozen
