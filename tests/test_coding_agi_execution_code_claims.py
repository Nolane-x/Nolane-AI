from __future__ import annotations

import subprocess

from cogcoder.organization.execution_tools import ExternalCoreExecutor
from cogcoder.organization.execution_types import ToolAction
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


def test_source_write_requires_active_code_claim_coverage(tmp_path):
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('task-write', title='edit app', plan_node_id='P1')
    runtime.tasks.lease('task-write', 'coding.backend.01')
    workspace = _workspace(tmp_path)
    executor = ExternalCoreExecutor(
        registry=runtime.registry,
        external_cores=runtime.external_cores,
        artifacts=runtime.artifacts,
        coding_patches=runtime.coding.patches,
        code_claims=runtime.coding.claims,
    )
    action = ToolAction.from_arguments(
        'filesystem', 'write_text', {'path': 'app.txt', 'content': 'changed\n'}, mutation_paths=('app.txt',),
    )

    denied = executor.invoke(agent_id='coding.backend.01', task_id='task-write', workspace=workspace, action=action)
    assert denied.success is False
    assert denied.failure_kind == 'code_claim_required'
    assert workspace.read_text('app.txt') == 'base\n'

    runtime.coding.claim_sources(agent_id='coding.backend.01', task_id='task-write', file_paths=('app.txt',))
    allowed = executor.invoke(agent_id='coding.backend.01', task_id='task-write', workspace=workspace, action=action)
    assert allowed.success is True
    assert workspace.read_text('app.txt') == 'changed\n'
    assert allowed.before_workspace_digest != allowed.after_workspace_digest
    workspace.close()
