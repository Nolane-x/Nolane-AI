from __future__ import annotations

import subprocess

from cogcoder.organization.execution import ExecutionState, ExecutionStepReceipt, ExecutionTerminalReceipt
from cogcoder.organization.execution_inference import DeterministicFixtureBackend
from cogcoder.organization.execution_types import ExecutionAction, ExecutionBudget, ToolAction
from cogcoder.organization.execution_workspace import RepositoryWorkspace
from cogcoder.organization.runtime import OrganizationRuntime


def _git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, text=True, capture_output=True).stdout.strip()


def _workspace(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    _git(source, 'init')
    _git(source, 'config', 'user.email', 'test@example.com')
    _git(source, 'config', 'user.name', 'Nolane Test')
    (source / 'app.txt').write_text('base\n')
    _git(source, 'add', 'app.txt')
    _git(source, 'commit', '-m', 'base')
    revision = _git(source, 'rev-parse', 'HEAD')
    return RepositoryWorkspace.create(source_repo=source, revision=revision, workspace_root=tmp_path / 'isolated')


def _budget():
    return ExecutionBudget(max_steps=6, max_tool_calls=4, max_external_core_calls=2, max_compute_units=6)


def test_coding_chief_directly_executes_bounded_source_task(tmp_path):
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('chief-task', title='edit app directly', plan_node_id='P1')
    runtime.tasks.lease('chief-task', 'coding.chief')
    runtime.coding.claim_sources(agent_id='coding.chief', task_id='chief-task', file_paths=('app.txt',))
    workspace = _workspace(tmp_path)
    backend = DeterministicFixtureBackend(actions=(
        ExecutionAction.tool(ToolAction.from_arguments(
            'filesystem', 'write_text', {'path': 'app.txt', 'content': 'chief-change\n'}, mutation_paths=('app.txt',),
        )),
        ExecutionAction.complete(reason='implementation-finished'),
    ))
    runtime.execution.bind_backend('coding.chief', backend)

    terminal = runtime.execution.execute(
        agent_id='coding.chief', task_id='chief-task', workspace=workspace,
        action_schema=('filesystem.write_text', 'complete'), budget=_budget(),
    )

    assert terminal.state is ExecutionState.COMPLETED
    assert terminal.tool_calls == 1
    assert len(terminal.decision_receipt_ids) == 2
    assert workspace.read_text('app.txt') == 'chief-change\n'
    assert runtime.tasks.get('chief-task').completed_by == 'coding.chief'
    assert runtime.coding.readiness_receipts() == ()
    workspace.close()


def test_central_abort_between_steps_prevents_next_side_effect(tmp_path):
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('abort-task', title='two edits', plan_node_id='P1')
    runtime.tasks.lease('abort-task', 'coding.backend.01')
    runtime.coding.claim_sources(
        agent_id='coding.backend.01', task_id='abort-task', file_paths=('app.txt', 'extra.txt'),
    )
    workspace = _workspace(tmp_path)
    backend = DeterministicFixtureBackend(actions=(
        ExecutionAction.tool(ToolAction.from_arguments(
            'filesystem', 'write_text', {'path': 'app.txt', 'content': 'first\n'}, mutation_paths=('app.txt',),
        )),
        ExecutionAction.tool(ToolAction.from_arguments(
            'filesystem', 'write_text', {'path': 'extra.txt', 'content': 'must-not-happen\n'}, mutation_paths=('extra.txt',),
        )),
        ExecutionAction.complete(reason='done'),
    ))
    runtime.execution.bind_backend('coding.backend.01', backend)
    session = runtime.execution.start(
        agent_id='coding.backend.01', task_id='abort-task', workspace=workspace,
        action_schema=('filesystem.write_text', 'complete'), budget=_budget(),
    )

    first = runtime.execution.step(session.session_id)
    assert isinstance(first, ExecutionStepReceipt)
    assert workspace.read_text('app.txt') == 'first\n'

    runtime.tasks.abort('abort-task', 'nolane.central', reason='Central stop')
    terminal = runtime.execution.step(session.session_id)

    assert isinstance(terminal, ExecutionTerminalReceipt)
    assert terminal.state is ExecutionState.ABORTED
    assert not (workspace.root / 'extra.txt').exists()
    workspace.close()
