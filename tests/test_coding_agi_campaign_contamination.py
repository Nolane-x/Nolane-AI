from __future__ import annotations

from cogcoder.organization.campaign_contamination import CampaignContaminationLedger, ContaminationKind
from cogcoder.organization.campaign_repository import RepositorySnapshotRegistry
from cogcoder.organization.campaign_tasks import CampaignPartition, CampaignTaskRegistry
from cogcoder.organization.evaluation_regimes import BenchmarkDomain


def _tasks():
    repos = RepositorySnapshotRegistry()
    repos.register(
        snapshot_id='repo-1', repository='example/project', revision='a' * 40,
        language='python', toolchain_digest='toolchain-v1', test_command_digest='pytest-v1',
        contamination_policy_digest='contam-v1', source_metadata={},
    )
    tasks = CampaignTaskRegistry(repositories=repos)
    heldout = tasks.register(
        task_id='heldout-1', domain=BenchmarkDomain.CODING, repository_snapshot_id='repo-1',
        objective='Secret heldout objective', acceptance_command_digest='secret-acceptance', difficulty='hard',
        allowed_tools=('pytest',), allowed_cores=('lsp',), compute_budget_units=100,
        tool_call_budget=20, external_core_budget=10, wall_clock_budget_ms=60_000,
        active_agent_budget=8, evaluator_protocol_version='campaign-eval-v1', contamination_tags=('secret-tag',),
    )
    train = tasks.register(
        task_id='train-1', domain=BenchmarkDomain.CODING, repository_snapshot_id='repo-1',
        objective='Visible training objective', acceptance_command_digest='train-acceptance', difficulty='easy',
        allowed_tools=('pytest',), allowed_cores=('lsp',), compute_budget_units=100,
        tool_call_budget=20, external_core_budget=10, wall_clock_budget_ms=60_000,
        active_agent_budget=8, evaluator_protocol_version='campaign-eval-v1', contamination_tags=('train-tag',),
    )
    tasks.assign_partition(heldout.task_id, CampaignPartition.HELDOUT)
    tasks.assign_partition(train.task_id, CampaignPartition.TRAIN)
    tasks.freeze_partitions()
    return tasks, heldout, train


def test_heldout_refs_in_training_or_distillation_are_quarantined():
    tasks, heldout, _ = _tasks()
    ledger = CampaignContaminationLedger(tasks=tasks)
    finding = ledger.scan(
        campaign_id='campaign-1', task_ids=('heldout-1', 'train-1'),
        training_refs=(heldout.task_id,), distillation_refs=(heldout.objective_digest,), personal_skill_refs=(),
    )
    assert finding.quarantined is True
    assert ContaminationKind.HELDOUT_TASK_REF in finding.kinds
    assert ContaminationKind.HELDOUT_OBJECTIVE_REF in finding.kinds
    assert finding.digest


def test_non_heldout_refs_do_not_create_false_contamination():
    tasks, _, train = _tasks()
    ledger = CampaignContaminationLedger(tasks=tasks)
    finding = ledger.scan(
        campaign_id='campaign-1', task_ids=('heldout-1', 'train-1'),
        training_refs=(train.task_id, train.objective_digest), distillation_refs=(), personal_skill_refs=(),
    )
    assert finding.quarantined is False
    assert finding.kinds == ()


def test_contamination_receipt_round_trips_exactly():
    tasks, heldout, _ = _tasks()
    ledger = CampaignContaminationLedger(tasks=tasks)
    original = ledger.scan(
        campaign_id='campaign-1', task_ids=('heldout-1',), training_refs=(),
        distillation_refs=(), personal_skill_refs=(heldout.acceptance_command_digest,),
    )
    restored = CampaignContaminationLedger.from_state(tasks=tasks, state=ledger.to_state())
    assert restored.latest_for('campaign-1') == original
