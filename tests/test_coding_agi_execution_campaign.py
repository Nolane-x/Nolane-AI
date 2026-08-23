from __future__ import annotations

import subprocess

from cogcoder.organization.campaign_tasks import CampaignPartition
from cogcoder.organization.evaluation_regimes import BenchmarkDomain, EvaluationMode
from cogcoder.organization.execution_campaign import ExecutionCampaignAdapter
from cogcoder.organization.execution_inference import DeterministicFixtureBackend
from cogcoder.organization.execution_types import ExecutionAction, ExecutionBudget, ToolAction
from cogcoder.organization.execution_workspace import RepositoryWorkspace
from cogcoder.organization.runtime import OrganizationRuntime


def _git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, text=True, capture_output=True).stdout.strip()


def _repo_and_workspace(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    _git(source, 'init')
    _git(source, 'config', 'user.email', 'test@example.com')
    _git(source, 'config', 'user.name', 'Nolane Test')
    (source / 'app.txt').write_text('base\n')
    _git(source, 'add', 'app.txt')
    _git(source, 'commit', '-m', 'base')
    revision = _git(source, 'rev-parse', 'HEAD')
    workspace = RepositoryWorkspace.create(source_repo=source, revision=revision, workspace_root=tmp_path / 'isolated')
    return source, revision, workspace


def test_heldout_smoke_execution_records_existing_campaign_run_without_inventing_pass_fail(tmp_path):
    runtime = OrganizationRuntime.first_generation()
    source, revision, workspace = _repo_and_workspace(tmp_path)
    campaign = runtime.evaluation_campaign
    campaign.repositories.register(
        snapshot_id='repo-smoke', repository=str(source), revision=revision, language='python',
        toolchain_digest='toolchain-v1', test_command_digest='tests-v1',
        contamination_policy_digest='contamination-v1', source_metadata={'kind': 'local-fixture'},
    )
    campaign.tasks.register(
        task_id='smoke-task', domain=BenchmarkDomain.CODING, repository_snapshot_id='repo-smoke',
        objective='write the requested repository file', acceptance_command_digest='accept-v1', difficulty='smoke',
        allowed_tools=('filesystem',), allowed_cores=('compiler',), compute_budget_units=8, tool_call_budget=4,
        external_core_budget=2, wall_clock_budget_ms=30000, active_agent_budget=1,
        evaluator_protocol_version='eval-v1', contamination_tags=('fresh-fixture',),
    )
    campaign.tasks.assign_partition('smoke-task', CampaignPartition.HELDOUT)
    campaign.tasks.freeze_partitions()
    campaign.create_campaign(
        campaign_id='campaign-smoke', benchmark_id='bridge-smoke', task_ids=('smoke-task',),
        modes=(EvaluationMode.SINGLE_AGENT,), freshness_epoch=1, runner_protocol_version='execution-v1',
    )
    campaign.freeze('campaign-smoke')
    campaign.start('campaign-smoke')
    campaign.runs.create_spec(
        run_id='run-smoke', campaign_id='campaign-smoke', task_id='smoke-task', mode=EvaluationMode.SINGLE_AGENT,
        producer_revision='producer-' + revision, environment_digest='env-v1', toolchain_digest='toolchain-v1',
    )

    runtime.tasks.add_task('smoke-task', title='campaign smoke task', plan_node_id='P1')
    runtime.tasks.lease('smoke-task', 'coding.backend.01')
    runtime.coding.claim_sources(agent_id='coding.backend.01', task_id='smoke-task', file_paths=('app.txt',))
    runtime.execution.bind_backend('coding.backend.01', DeterministicFixtureBackend(actions=(
        ExecutionAction.tool(ToolAction.from_arguments(
            'filesystem', 'write_text', {'path': 'app.txt', 'content': 'smoke-pass\n'}, mutation_paths=('app.txt',),
        )),
        ExecutionAction.complete(reason='smoke-finished'),
    )))
    terminal = runtime.execution.execute(
        agent_id='coding.backend.01', task_id='smoke-task', workspace=workspace,
        action_schema=('filesystem.write_text', 'complete'),
        budget=ExecutionBudget(max_steps=4, max_tool_calls=2, max_external_core_calls=1, max_compute_units=4),
    )

    receipt = ExecutionCampaignAdapter(campaign.runs).record_terminal_result(
        run_id='run-smoke', terminal=terminal, evaluator_passed=True, false_accepts=0, regressions=0,
        energy_joules=None, active_agents=1,
    )

    assert receipt.passed is True
    assert receipt.compute_units == terminal.compute_units
    assert receipt.tool_calls == terminal.tool_calls
    assert receipt.output_artifact_ids == terminal.output_artifact_ids
    assert campaign.runs.get_receipt('run-smoke') == receipt
    workspace.close()
