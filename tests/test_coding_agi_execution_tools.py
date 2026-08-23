from __future__ import annotations

import subprocess
import sys

from cogcoder.organization.execution_tools import CoreInvocationReceipt, ExternalCoreExecutor
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


def _executor(runtime):
    return ExternalCoreExecutor(
        registry=runtime.registry,
        external_cores=runtime.external_cores,
        artifacts=runtime.artifacts,
        coding_patches=runtime.coding.patches,
        code_claims=runtime.coding.claims,
    )


def test_executor_rejects_authorized_tool_without_current_task_lease(tmp_path):
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('task-no-lease', title='read without lease', plan_node_id='P1')
    workspace = _workspace(tmp_path)

    receipt = _executor(runtime).invoke(
        agent_id='coding.backend.01',
        task_id='task-no-lease',
        workspace=workspace,
        action=ToolAction.from_arguments('filesystem', 'read_text', {'path': 'app.txt'}),
    )

    assert receipt.success is False
    assert receipt.authorized is True
    assert receipt.failure_kind == 'task_lease_required'
    assert runtime.artifacts.get(receipt.evidence_artifact_id).kind == 'execution-core-failure'
    workspace.close()


def test_unauthorized_core_fails_closed_and_preserves_failure_receipt(tmp_path):
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('task-1', title='read repository', plan_node_id='P1')
    runtime.tasks.lease('task-1', 'coding.backend.01')
    workspace = _workspace(tmp_path)

    receipt = _executor(runtime).invoke(
        agent_id='coding.backend.01',
        task_id='task-1',
        workspace=workspace,
        action=ToolAction.from_arguments('browser', 'open', {'url': 'https://example.invalid'}),
    )

    assert receipt.success is False
    assert receipt.authorized is False
    assert receipt.failure_kind == 'permission_denied'
    assert runtime.artifacts.get(receipt.evidence_artifact_id).kind == 'execution-core-failure'
    assert CoreInvocationReceipt.from_state(receipt.to_state()) == receipt
    workspace.close()


def test_authorized_filesystem_read_creates_output_and_coding_tool_receipt(tmp_path):
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('task-1', title='read repository', plan_node_id='P1')
    runtime.tasks.lease('task-1', 'coding.backend.01')
    workspace = _workspace(tmp_path)

    receipt = _executor(runtime).invoke(
        agent_id='coding.backend.01',
        task_id='task-1',
        workspace=workspace,
        action=ToolAction.from_arguments('filesystem', 'read_text', {'path': 'app.txt'}),
    )

    assert receipt.success is True
    assert receipt.authorized is True
    assert receipt.output_artifact_ids
    assert runtime.artifacts.get(receipt.output_artifact_ids[0]).content == 'base\n'
    assert receipt.mirrored_tool_receipt_id is not None
    assert runtime.coding.patches.get_tool_receipt(receipt.mirrored_tool_receipt_id).success is True
    workspace.close()


def test_terminal_command_runs_in_disposable_copy_and_cannot_mutate_source_workspace(tmp_path):
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('task-terminal', title='bounded terminal', plan_node_id='P1')
    runtime.tasks.lease('task-terminal', 'coding.backend.01')
    workspace = _workspace(tmp_path)

    receipt = _executor(runtime).invoke(
        agent_id='coding.backend.01',
        task_id='task-terminal',
        workspace=workspace,
        action=ToolAction.from_arguments(
            'terminal',
            'run',
            {'argv': [sys.executable, '-c', "open('app.txt','w').write('bypass\\n')"]},
        ),
    )

    assert receipt.success is True
    assert workspace.read_text('app.txt') == 'base\n'
    assert receipt.before_workspace_digest == receipt.after_workspace_digest
    workspace.close()
