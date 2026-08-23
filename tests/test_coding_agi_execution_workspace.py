from __future__ import annotations

import subprocess

import pytest

from cogcoder.organization.execution_workspace import RepositoryWorkspace


def _git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, text=True, capture_output=True).stdout.strip()


def _tiny_repo(tmp_path):
    repo = tmp_path / 'source'
    repo.mkdir()
    _git(repo, 'init')
    _git(repo, 'config', 'user.email', 'test@example.com')
    _git(repo, 'config', 'user.name', 'Nolane Test')
    (repo / 'app.txt').write_text('base\n')
    _git(repo, 'add', 'app.txt')
    _git(repo, 'commit', '-m', 'base')
    return repo, _git(repo, 'rev-parse', 'HEAD')


def test_workspace_uses_detached_exact_revision_and_never_mutates_source(tmp_path):
    source, revision = _tiny_repo(tmp_path)
    workspace = RepositoryWorkspace.create(
        source_repo=source,
        revision=revision,
        workspace_root=tmp_path / 'isolated',
    )
    before = workspace.digest
    workspace.write_text('app.txt', 'changed\n')

    assert workspace.base_revision == revision
    assert workspace.read_text('app.txt') == 'changed\n'
    assert (source / 'app.txt').read_text() == 'base\n'
    assert workspace.digest != before
    assert _git(source, 'rev-parse', 'HEAD') == revision
    workspace.close()


def test_workspace_rejects_path_escape(tmp_path):
    source, revision = _tiny_repo(tmp_path)
    workspace = RepositoryWorkspace.create(source_repo=source, revision=revision, workspace_root=tmp_path / 'isolated')

    with pytest.raises(PermissionError, match='workspace'):
        workspace.resolve_repo_path('../escape.txt')
    with pytest.raises(PermissionError, match='workspace'):
        workspace.resolve_repo_path(str(tmp_path / 'outside.txt'))

    workspace.close()
