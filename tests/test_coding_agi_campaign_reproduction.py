from __future__ import annotations

import copy
import pytest

from cogcoder.organization.campaign import EvaluationCampaignControlPlane
from cogcoder.organization.campaign_reproduction import CampaignReproductionLedger
from cogcoder.organization.campaign_repository import RepositorySnapshotRegistry
from cogcoder.organization.campaign_tasks import CampaignPartition, CampaignTaskRegistry
from cogcoder.organization.evaluation_regimes import BenchmarkDomain, EvaluationMode
from cogcoder.organization.runtime import OrganizationRuntime


def _fixture():
    runtime = OrganizationRuntime.first_generation()
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
        modes=(EvaluationMode.ORGANIZATION,), freshness_epoch=1, runner_protocol_version='campaign-runner-v1',
    )
    campaigns.freeze('campaign-1')
    artifact = runtime.artifacts.put(
        kind='campaign-bundle', producer_agent_id='verification.integration-e2e.01',
        content='bundle', evidence_refs=(), metadata={},
    )
    return runtime, campaigns, artifact


def test_reproduction_requires_evaluator_outside_permanent_organization():
    runtime, campaigns, artifact = _fixture()
    ledger = CampaignReproductionLedger(registry=runtime.registry, artifacts=runtime.artifacts, campaigns=campaigns)
    package = ledger.create_package(
        package_id='pkg-1', campaign_id='campaign-1', observation_ids=('observation-1',),
        source_revision_digests=('a' * 40,), task_set_digest='task-set-v1',
        runner_protocol_digest='runner-protocol-v1', environment_digest='env-v1',
        command_manifest_digest='commands-v1', artifact_ids=(artifact.artifact_id,),
    )
    with pytest.raises(PermissionError):
        ledger.record_reproduction(
            reproduction_id='repro-1', package_id=package.package_id,
            evaluator_id='verification.integration-e2e.01', reproduced=True,
            artifact_bundle_digest=package.artifact_bundle_digest,
        )
    receipt = ledger.record_reproduction(
        reproduction_id='repro-1', package_id=package.package_id,
        evaluator_id='external-lab-001', reproduced=True,
        artifact_bundle_digest=package.artifact_bundle_digest,
    )
    assert receipt.independent is True
    assert receipt.reproduced is True


def test_reproduction_snapshot_detects_tampering():
    runtime, campaigns, artifact = _fixture()
    ledger = CampaignReproductionLedger(registry=runtime.registry, artifacts=runtime.artifacts, campaigns=campaigns)
    package = ledger.create_package(
        package_id='pkg-1', campaign_id='campaign-1', observation_ids=('observation-1',),
        source_revision_digests=('a' * 40,), task_set_digest='task-set-v1',
        runner_protocol_digest='runner-protocol-v1', environment_digest='env-v1',
        command_manifest_digest='commands-v1', artifact_ids=(artifact.artifact_id,),
    )
    ledger.record_reproduction(
        reproduction_id='repro-1', package_id=package.package_id,
        evaluator_id='external-lab-001', reproduced=True,
        artifact_bundle_digest=package.artifact_bundle_digest,
    )
    state = ledger.to_state()
    restored = CampaignReproductionLedger.from_state(
        registry=runtime.registry, artifacts=runtime.artifacts, campaigns=campaigns, state=state,
    )
    assert restored.get_package('pkg-1') == package
    tampered = copy.deepcopy(state)
    tampered['packages'][0]['environment_digest'] = 'tampered'
    with pytest.raises(ValueError):
        CampaignReproductionLedger.from_state(
            registry=runtime.registry, artifacts=runtime.artifacts, campaigns=campaigns, state=tampered,
        )
