from __future__ import annotations

import pytest

from cogcoder.organization.campaign_repository import RepositorySnapshotRegistry
from cogcoder.organization.campaign_tasks import CampaignPartition, CampaignTaskRegistry
from cogcoder.organization.evaluation_regimes import BenchmarkDomain


def _snapshot(registry: RepositorySnapshotRegistry, *, snapshot_id: str = 'repo-1', revision: str = 'a' * 40):
    return registry.register(
        snapshot_id=snapshot_id,
        repository='example/project',
        revision=revision,
        language='python',
        toolchain_digest='toolchain-v1',
        test_command_digest='pytest-digest',
        contamination_policy_digest='contamination-v1',
        source_metadata={'license': 'MIT'},
    )


def _task(tasks: CampaignTaskRegistry, *, task_id: str = 'task-1'):
    return tasks.register(
        task_id=task_id,
        domain=BenchmarkDomain.CODING,
        repository_snapshot_id='repo-1',
        objective='Fix the heldout bug without changing public behavior.',
        acceptance_command_digest='acceptance-v1',
        difficulty='medium',
        allowed_tools=('pytest', 'git'),
        allowed_cores=('lsp', 'ast'),
        compute_budget_units=100,
        tool_call_budget=20,
        external_core_budget=10,
        wall_clock_budget_ms=60_000,
        active_agent_budget=8,
        evaluator_protocol_version='campaign-eval-v1',
        contamination_tags=('bug-17',),
    )


def test_repository_snapshot_requires_exact_immutable_revision():
    registry = RepositorySnapshotRegistry()
    for movable in ('main', 'master', 'HEAD', 'latest', ''):
        with pytest.raises(ValueError):
            _snapshot(registry, snapshot_id='bad-' + (movable or 'empty'), revision=movable)
    row = _snapshot(registry)
    assert row.revision == 'a' * 40
    assert row.digest


def test_repository_and_task_ids_cannot_be_rebound():
    repos = RepositorySnapshotRegistry()
    _snapshot(repos)
    assert _snapshot(repos) == repos.get('repo-1')
    with pytest.raises(ValueError):
        repos.register(
            snapshot_id='repo-1', repository='example/project', revision='b' * 40,
            language='python', toolchain_digest='toolchain-v1', test_command_digest='pytest-digest',
            contamination_policy_digest='contamination-v1', source_metadata={'license': 'MIT'},
        )

    tasks = CampaignTaskRegistry(repositories=repos)
    first = _task(tasks)
    assert _task(tasks) == first
    with pytest.raises(ValueError):
        tasks.register(**{**first.registration_kwargs(), 'objective': 'different objective'})


def test_partition_assignment_is_exactly_once_and_freezes():
    repos = RepositorySnapshotRegistry(); _snapshot(repos)
    tasks = CampaignTaskRegistry(repositories=repos); task = _task(tasks)
    tasks.assign_partition(task.task_id, CampaignPartition.HELDOUT)
    assert tasks.partition_of(task.task_id) is CampaignPartition.HELDOUT
    digest = tasks.freeze_partitions()
    assert digest
    with pytest.raises(PermissionError):
        tasks.assign_partition(task.task_id, CampaignPartition.TRAIN)
    restored = CampaignTaskRegistry.from_state(repositories=repos, state=tasks.to_state())
    assert restored.partition_digest == digest
    assert restored.partition_of(task.task_id) is CampaignPartition.HELDOUT
