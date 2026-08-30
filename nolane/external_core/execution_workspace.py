from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from nolane.core.canonical_digest import canonical_digest


COMPONENT_ID = "external.execution.workspace"
COMPONENT_VERSION = "0.0.3"
MIGRATED_FROM = "cogcoder.organization.execution_workspace"

__all__ = [
    "WorkspaceCommandResult",
    "WorkspaceCheckpoint",
    "RepositoryWorkspace",
]


@dataclass(frozen=True, slots=True)
class WorkspaceCommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass(frozen=True, slots=True)
class WorkspaceCheckpoint:
    """Ephemeral rollback point bound to one isolated RepositoryWorkspace."""

    checkpoint_id: str
    workspace_root: str
    workspace_digest: str
    label: str
    snapshot_root: Path


class RepositoryWorkspace:
    def __init__(self, *, source_repo: Path, root: Path, base_revision: str) -> None:
        self.source_repo = source_repo.resolve()
        self.root = root.resolve()
        self.base_revision = str(base_revision)
        self._closed = False
        self._checkpoint_counter = 0
        self._checkpoint_roots: set[Path] = set()

    @staticmethod
    def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ['git', '-C', str(repo), *args],
            check=check,
            text=True,
            capture_output=True,
        )

    @classmethod
    def create(
        cls,
        *,
        source_repo: str | Path,
        revision: str,
        workspace_root: str | Path,
    ) -> 'RepositoryWorkspace':
        source = Path(source_repo).resolve()
        target = Path(workspace_root).resolve()
        if not source.is_dir():
            raise FileNotFoundError(f'source repository not found: {source}')
        top = cls._git(source, 'rev-parse', '--show-toplevel').stdout.strip()
        source = Path(top).resolve()
        resolved_revision = cls._git(source, 'rev-parse', f'{revision}^{{commit}}').stdout.strip()
        if len(resolved_revision) != 40:
            raise ValueError('repository revision did not resolve to a full commit id')
        if target == source or source in target.parents or target in source.parents:
            raise PermissionError('workspace root must be isolated from source repository')
        if target.exists():
            if any(target.iterdir()) if target.is_dir() else True:
                raise FileExistsError(f'workspace root already exists and is non-empty: {target}')
            target.rmdir()
        target.parent.mkdir(parents=True, exist_ok=True)
        cls._git(source, 'worktree', 'add', '--detach', str(target), resolved_revision)
        workspace = cls(source_repo=source, root=target, base_revision=resolved_revision)
        head = workspace._git(workspace.root, 'rev-parse', 'HEAD').stdout.strip()
        if head != resolved_revision:
            workspace.close()
            raise RuntimeError('isolated workspace checked out unexpected revision')
        return workspace

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError('repository workspace is closed')

    def resolve_repo_path(self, relative_path: str | Path) -> Path:
        self._ensure_open()
        raw = Path(relative_path)
        if raw.is_absolute():
            raise PermissionError('path escapes isolated workspace')
        candidate = (self.root / raw).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise PermissionError('path escapes isolated workspace') from exc
        return candidate

    def _payload_rows(self) -> list[dict[str, str | int]]:
        rows: list[dict[str, str | int]] = []
        for path in sorted(self.root.rglob('*'), key=lambda item: item.relative_to(self.root).as_posix()):
            relative = path.relative_to(self.root).as_posix()
            if relative == '.git' or relative.startswith('.git/'):
                continue
            if path.is_symlink():
                rows.append({'path': relative, 'kind': 'symlink', 'target': str(path.readlink())})
            elif path.is_dir():
                rows.append({'path': relative, 'kind': 'directory'})
            elif path.is_file():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                rows.append({'path': relative, 'kind': 'file', 'size': path.stat().st_size, 'sha256': digest})
            else:
                raise RuntimeError(f'unsupported workspace payload entry: {relative}')
        return rows

    @property
    def digest(self) -> str:
        self._ensure_open()
        status = self._git(self.root, 'status', '--porcelain=v1', '--untracked-files=all').stdout
        return canonical_digest({
            'base_revision': self.base_revision,
            'head': self._git(self.root, 'rev-parse', 'HEAD').stdout.strip(),
            'status': status,
            'payload': self._payload_rows(),
        })

    def read_text(self, path: str | Path, *, encoding: str = 'utf-8') -> str:
        target = self.resolve_repo_path(path)
        return target.read_text(encoding=encoding)

    def write_text(self, path: str | Path, content: str, *, encoding: str = 'utf-8') -> None:
        target = self.resolve_repo_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding=encoding)

    def append_text(self, path: str | Path, content: str, *, encoding: str = 'utf-8') -> None:
        target = self.resolve_repo_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('a', encoding=encoding) as handle:
            handle.write(str(content))

    @staticmethod
    def _copy_entry(source: Path, target: Path) -> None:
        if source.is_symlink():
            target.symlink_to(source.readlink(), target_is_directory=source.is_dir())
        elif source.is_dir():
            shutil.copytree(source, target, symlinks=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target, follow_symlinks=False)

    def checkpoint(self, *, label: str = 'before-action') -> WorkspaceCheckpoint:
        """Capture the full worktree payload (excluding Git administrative data).

        The checkpoint is intentionally ephemeral: it is a local transaction undo
        boundary, while durable evidence belongs in the acting protocol/artifact store.
        """

        self._ensure_open()
        clean_label = str(label).strip()
        if not clean_label:
            raise ValueError('workspace checkpoint label must be explicit')
        before = self.digest
        self._checkpoint_counter += 1
        checkpoint_digest = canonical_digest({
            'workspace_root': str(self.root),
            'workspace_digest': before,
            'label': clean_label,
            'counter': self._checkpoint_counter,
        })
        snapshot_root = Path(tempfile.mkdtemp(prefix='nolane-workspace-checkpoint-')).resolve()
        try:
            for child in self.root.iterdir():
                if child.name == '.git':
                    continue
                self._copy_entry(child, snapshot_root / child.name)
        except Exception:
            shutil.rmtree(snapshot_root, ignore_errors=True)
            raise
        self._checkpoint_roots.add(snapshot_root)
        return WorkspaceCheckpoint(
            checkpoint_id='workspace-checkpoint-' + checkpoint_digest[:24],
            workspace_root=str(self.root),
            workspace_digest=before,
            label=clean_label,
            snapshot_root=snapshot_root,
        )

    def _validate_checkpoint(self, checkpoint: WorkspaceCheckpoint) -> Path:
        self._ensure_open()
        if str(self.root) != str(checkpoint.workspace_root):
            raise PermissionError('workspace checkpoint belongs to a different workspace')
        snapshot = checkpoint.snapshot_root.resolve()
        if snapshot not in self._checkpoint_roots or not snapshot.is_dir():
            raise FileNotFoundError('workspace checkpoint snapshot is unavailable')
        return snapshot

    def restore(self, checkpoint: WorkspaceCheckpoint) -> str:
        """Restore a checkpoint and prove restoration by recomputing workspace digest."""

        snapshot = self._validate_checkpoint(checkpoint)
        for child in tuple(self.root.iterdir()):
            if child.name == '.git':
                continue
            if child.is_symlink() or child.is_file():
                child.unlink(missing_ok=True)
            else:
                shutil.rmtree(child)
        for child in snapshot.iterdir():
            self._copy_entry(child, self.root / child.name)
        restored = self.digest
        if restored != checkpoint.workspace_digest:
            raise RuntimeError('workspace rollback failed digest verification')
        return restored

    def release_checkpoint(self, checkpoint: WorkspaceCheckpoint) -> None:
        snapshot = self._validate_checkpoint(checkpoint)
        shutil.rmtree(snapshot, ignore_errors=True)
        self._checkpoint_roots.discard(snapshot)

    def run_argv(
        self,
        argv: Sequence[str],
        *,
        timeout_seconds: float = 30.0,
        max_output_chars: int = 200_000,
        check: bool = False,
    ) -> WorkspaceCommandResult:
        self._ensure_open()
        args = tuple(str(x) for x in argv)
        if not args or any('\x00' in x for x in args):
            raise ValueError('workspace command requires a valid argv sequence')
        if timeout_seconds <= 0 or max_output_chars <= 0:
            raise ValueError('workspace command bounds must be positive')
        try:
            proc = subprocess.run(
                list(args),
                cwd=self.root,
                text=True,
                capture_output=True,
                timeout=float(timeout_seconds),
                check=False,
            )
            result = WorkspaceCommandResult(
                argv=args,
                returncode=int(proc.returncode),
                stdout=proc.stdout[:max_output_chars],
                stderr=proc.stderr[:max_output_chars],
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or '')
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or '')
            result = WorkspaceCommandResult(
                argv=args,
                returncode=124,
                stdout=stdout[:max_output_chars],
                stderr=stderr[:max_output_chars],
                timed_out=True,
            )
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, args, output=result.stdout, stderr=result.stderr)
        return result

    def close(self) -> None:
        if self._closed:
            return
        for snapshot in tuple(self._checkpoint_roots):
            shutil.rmtree(snapshot, ignore_errors=True)
        self._checkpoint_roots.clear()
        if self.root.exists():
            proc = self._git(self.source_repo, 'worktree', 'remove', '--force', str(self.root), check=False)
            if proc.returncode != 0 and self.root.exists():
                shutil.rmtree(self.root, ignore_errors=True)
            self._git(self.source_repo, 'worktree', 'prune', check=False)
        self._closed = True
