from __future__ import annotations

import subprocess

from cogcoder.organization.execution import ExecutionState, ExecutionStepReceipt
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
    (source / 'log.txt').write_text('')
    _git(source, 'add', 'log.txt')
    _git(source, 'commit', '-m', 'base')
    revision = _git(source, 'rev-parse', 'HEAD')
    return RepositoryWorkspace.create(source_repo=source, revision=revision, workspace_root=tmp_path / 'isolated')


def _backend():
    return DeterministicFixtureBackend(actions=(
        ExecutionAction.tool(ToolAction.from_arguments(
            'filesystem', 'append_text', {'path': 'log.txt', 'content': 'x'}, mutation_paths=('log.txt',),
        )),
        ExecutionAction.complete(reason='done'),
    ))


def test_runtime_execution_snapshot_restores_without_replaying_completed_side_effect(tmp_path):
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('resume-task', title='append once', plan_node_id='P1')
    runtime.tasks.lease('resume-task', 'coding.backend.01')
    runtime.coding.claim_sources(agent_id='coding.backend.01', task_id='resume-task', file_paths=('log.txt',))
    workspace = _workspace(tmp_path)
    runtime.execution.bind_backend('coding.backend.01', _backend())
    session = runtime.execution.start(
        agent_id='coding.backend.01', task_id='resume-task', workspace=workspace,
        action_schema=('filesystem.append_text', 'complete'),
        budget=ExecutionBudget(max_steps=4, max_tool_calls=2, max_external_core_calls=1, max_compute_units=4),
    )
    first = runtime.execution.step(session.session_id)
    assert isinstance(first, ExecutionStepReceipt)
    assert workspace.read_text('log.txt') == 'x'

    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(state)
    restored.execution.bind_backend('coding.backend.01', _backend())
    restored.execution.attach_workspace(session.session_id, workspace)
    terminal = restored.execution.run(session.session_id)

    assert terminal.state is ExecutionState.COMPLETED
    assert workspace.read_text('log.txt') == 'x'
    assert restored.execution.get_session(session.session_id).step_index == 2
    workspace.close()


def test_historical_snapshot_without_execution_key_restores_empty_bridge():
    runtime = OrganizationRuntime.first_generation()
    state = runtime.to_state()
    state.pop('execution')

    restored = OrganizationRuntime.from_state(state)

    assert restored.execution.sessions() == ()
    assert restored.execution.terminal_receipts() == ()
