from __future__ import annotations

from cogcoder.organization.campaign_tasks import CampaignPartition
from cogcoder.organization.evaluation_regimes import BenchmarkDomain, EvidenceProvenanceClass, EvaluationMode
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord


def test_ingest_receipt_survives_exact_runtime_snapshot_restore():
    runtime = OrganizationRuntime.first_generation()
    layer = runtime.evaluation_campaign
    layer.repositories.register(
        snapshot_id='repo-1', repository='example/project', revision='a' * 40,
        language='python', toolchain_digest='toolchain-v1', test_command_digest='pytest-v1',
        contamination_policy_digest='contam-v1', source_metadata={},
    )
    layer.tasks.register(
        task_id='task-1', domain=BenchmarkDomain.CODING, repository_snapshot_id='repo-1',
        objective='Fix heldout bug', acceptance_command_digest='accept-v1', difficulty='medium',
        allowed_tools=('pytest',), allowed_cores=('lsp',), compute_budget_units=100,
        tool_call_budget=20, external_core_budget=10, wall_clock_budget_ms=60_000,
        active_agent_budget=8, evaluator_protocol_version='campaign-eval-v1', contamination_tags=(),
    )
    layer.tasks.assign_partition('task-1', CampaignPartition.HELDOUT)
    layer.tasks.freeze_partitions()
    layer.create_campaign(
        campaign_id='campaign-1', benchmark_id='real-repo-coding-v1', task_ids=('task-1',),
        modes=(EvaluationMode.ORGANIZATION,), freshness_epoch=1, runner_protocol_version='campaign-runner-v1',
    )
    layer.freeze('campaign-1'); layer.start('campaign-1')
    artifact = runtime.artifacts.put(
        kind='campaign-run-evidence', producer_agent_id='verification.integration-e2e.01',
        content='evidence-task-1', evidence_refs=(), metadata={'task_id': 'task-1'},
    )
    layer.runs.create_spec(
        run_id='run-1', campaign_id='campaign-1', task_id='task-1', mode=EvaluationMode.ORGANIZATION,
        producer_revision='candidate-sha', environment_digest='env-v1', toolchain_digest='toolchain-v1',
    )
    layer.runs.record_result(
        run_id='run-1', passed=True, false_accepts=0, regressions=0,
        compute_units=40, tool_calls=5, external_core_calls=2, wall_clock_ms=10_000,
        energy_joules=20.0, active_agents=4, output_artifact_ids=(artifact.artifact_id,),
        termination_reason='completed',
    )
    layer.contamination.scan(
        campaign_id='campaign-1', task_ids=('task-1',), training_refs=(),
        distillation_refs=(), personal_skill_refs=(),
    )
    receipt = layer.ingestor.ingest_mode(
        campaign_id='campaign-1', mode=EvaluationMode.ORGANIZATION,
        provenance_class=EvidenceProvenanceClass.INTERNAL_REAL_REPOSITORY,
        evidence=EvidenceRecord('campaign-evidence-1', 'verification.integration-e2e.01', True),
        external_evaluator_id=None,
    )

    restored = OrganizationRuntime.from_state(runtime.to_state())
    assert restored.evaluation_campaign.ingestor.get_receipt(receipt.receipt_id) == receipt
