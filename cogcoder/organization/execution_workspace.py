from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .types import canonical_digest


@dataclass(frozen=True, slots=True)
class WorkspaceCommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class RepositoryWorkspace:
    def __init__(self, *, source_repo: Path, root: Path, base_revision: str) -> None:
        self.source_repo = source_repo.resolve()
        self.root = root.resolve()
        self.base_revision = str(base_revision)
        self._closed = False

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

    @property
    def digest(self) -> str:
        self._ensure_open()
        status = self._git(self.root, 'status', '--porcelain=v1', '--untracked-files=all').stdout
        files = self._git(self.root, 'ls-files', '-co', '--exclude-standard').stdout.splitlines()
        rows: list[dict[str, str | int]] = []
        for relative in sorted(set(x for x in files if x.strip())):
            path = self.resolve_repo_path(relative)
            if path.is_symlink():
                rows.append({'path': relative, 'kind': 'symlink', 'target': str(path.readlink())})
            elif path.is_file():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                rows.append({'path': relative, 'kind': 'file', 'size': path.stat().st_size, 'sha256': digest})
        return canonical_digest({
            'base_revision': self.base_revision,
            'head': self._git(self.root, 'rev-parse', 'HEAD').stdout.strip(),
            'status': status,
            'files': rows,
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
        if self.root.exists():
            proc = self._git(self.source_repo, 'worktree', 'remove', '--force', str(self.root), check=False)
            if proc.returncode != 0 and self.root.exists():
                shutil.rmtree(self.root, ignore_errors=True)
            self._git(self.source_repo, 'worktree', 'prune', check=False)
        self._closed = True
