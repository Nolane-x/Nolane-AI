from __future__ import annotations

from cogcoder.organization.evaluation_claims import ClaimClass, ClaimDisposition
from cogcoder.organization.evaluation_regimes import BenchmarkDomain, EvaluationMode
from cogcoder.organization.campaign_tasks import CampaignPartition
from cogcoder.organization.runtime import OrganizationRuntime


def test_pre_campaign_snapshot_restores_empty_campaign_layer():
    runtime = OrganizationRuntime.first_generation()
    state = runtime.to_state()
    state.pop('evaluation_campaign', None)
    restored = OrganizationRuntime.from_state(state)
    assert restored.evaluation_campaign.is_empty()
    assert len(restored.registry.identities()) == 67


def test_campaign_snapshot_round_trips_without_mutating_neural_or_parameter_state():
    runtime = OrganizationRuntime.first_generation()
    before = {
        row.agent_id: (row.neural_version, row.parameter_accounting.to_state())
        for row in runtime.registry.identities()
    }
    layer = runtime.evaluation_campaign
    layer.repositories.register(
        snapshot_id='repo-1', repository='example/project', revision='a' * 40,
        language='python', toolchain_digest='toolchain-v1', test_command_digest='pytest-v1',
        contamination_policy_digest='contam-v1', source_metadata={},
    )
    layer.tasks.register(
        task_id='task-1', domain=BenchmarkDomain.CODING, repository_snapshot_id='repo-1',
        objective='Fix bug', acceptance_command_digest='accept-v1', difficulty='medium',
        allowed_tools=('pytest',), allowed_cores=('lsp',), compute_budget_units=100,
        tool_call_budget=20, external_core_budget=10, wall_clock_budget_ms=60_000,
        active_agent_budget=8, evaluator_protocol_version='campaign-eval-v1', contamination_tags=(),
    )
    layer.tasks.assign_partition('task-1', CampaignPartition.HELDOUT); layer.tasks.freeze_partitions()
    layer.create_campaign(
        campaign_id='campaign-1', benchmark_id='real-repo-coding-v1', task_ids=('task-1',),
        modes=(EvaluationMode.ORGANIZATION,), freshness_epoch=1, runner_protocol_version='campaign-runner-v1',
    )
    layer.freeze('campaign-1')
    restored = OrganizationRuntime.from_state(runtime.to_state())
    assert restored.evaluation_campaign.get('campaign-1') == layer.get('campaign-1')
    after = {
        row.agent_id: (row.neural_version, row.parameter_accounting.to_state())
        for row in restored.registry.identities()
    }
    assert after == before


def test_campaign_layer_cannot_unlock_hard_disabled_claim_classes():
    runtime = OrganizationRuntime.first_generation()
    agi = runtime.evaluation_scaling.claims.assess('campaign-agi-attempt', ClaimClass.AGI)
    frontier = runtime.evaluation_scaling.claims.assess('campaign-frontier-attempt', ClaimClass.FRONTIER_EQUIVALENCE)
    assert agi.disposition is ClaimDisposition.BLOCKED
    assert frontier.disposition is ClaimDisposition.BLOCKED
    assert agi.override_effective is False
    assert frontier.override_effective is False
