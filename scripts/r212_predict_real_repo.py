from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

from cogcoder.r212_real_repo_localizer import rank_repository_files
from cogcoder.r212_real_repo_protocol import PublicRepoTask, validate_predictor_payload


def validate_public_manifest(rows: Iterable[dict[str, Any]]) -> list[PublicRepoTask]:
    tasks = [validate_predictor_payload(row) for row in rows]
    ids = [task.instance_id for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate instance_id in public manifest')
    return tasks


def _run_git(args: list[str], *, cwd: Path | None = None, timeout_seconds: int = 180) -> str:
    result = subprocess.run(
        ['git', *args],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout_seconds,
        env={**dict(__import__('os').environ), 'GIT_TERMINAL_PROMPT': '0'},
    )
    return result.stdout.strip()


def materialize_git_commit(remote_url: str, commit: str, dest: Path, *, timeout_seconds: int = 180) -> str:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    _run_git(['init', '-q'], cwd=dest, timeout_seconds=timeout_seconds)
    _run_git(['remote', 'add', 'origin', remote_url], cwd=dest, timeout_seconds=timeout_seconds)
    _run_git(
        ['-c', 'advice.detachedHead=false', 'fetch', '--depth=1', 'origin', commit],
        cwd=dest,
        timeout_seconds=timeout_seconds,
    )
    _run_git(['checkout', '-q', '--detach', 'FETCH_HEAD'], cwd=dest, timeout_seconds=timeout_seconds)
    got = _run_git(['rev-parse', 'HEAD'], cwd=dest, timeout_seconds=timeout_seconds).lower()
    if got != commit.lower():
        raise RuntimeError(f'commit mismatch: expected {commit}, got {got}')
    return got


def _ranking_digest(path_top: list[str], hybrid_top: list[str]) -> str:
    raw = json.dumps({'path': path_top, 'hybrid': hybrid_top}, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def predict_task(task: PublicRepoTask, *, checkout_root: Path, timeout_seconds: int = 240) -> dict[str, Any]:
    dest = checkout_root / task.instance_id.replace('/', '__')
    started = time.monotonic()
    try:
        got = materialize_git_commit(
            f'https://github.com/{task.repo}.git',
            task.base_commit,
            dest,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        shutil.rmtree(dest, ignore_errors=True)
        return {
            'instance_id': task.instance_id,
            'repo': task.repo,
            'base_commit': task.base_commit,
            'status': 'materialize_failed',
            'error_type': type(exc).__name__,
            'path_top20': [],
            'hybrid_top20': [],
            'deterministic': False,
            'ranking_sha256': None,
            'elapsed_seconds': round(time.monotonic() - started, 3),
        }

    try:
        path_rank = rank_repository_files(dest, task.problem_statement, mode='path', top_k=20)
        hybrid_rank = rank_repository_files(dest, task.problem_statement, mode='hybrid', top_k=20)
        path_top = [row.path for row in path_rank]
        hybrid_top = [row.path for row in hybrid_rank]
        digest = _ranking_digest(path_top, hybrid_top)

        repeat_path = [row.path for row in rank_repository_files(dest, task.problem_statement, mode='path', top_k=20)]
        repeat_hybrid = [row.path for row in rank_repository_files(dest, task.problem_statement, mode='hybrid', top_k=20)]
        repeat_digest = _ranking_digest(repeat_path, repeat_hybrid)
        deterministic = digest == repeat_digest
        return {
            'instance_id': task.instance_id,
            'repo': task.repo,
            'base_commit': task.base_commit,
            'checked_out_commit': got,
            'status': 'ok',
            'path_top20': path_top,
            'hybrid_top20': hybrid_top,
            'deterministic': deterministic,
            'ranking_sha256': digest,
            'candidate_files': max(len(path_rank), len(hybrid_rank)),
            'elapsed_seconds': round(time.monotonic() - started, 3),
        }
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--checkout-root')
    parser.add_argument('--timeout-seconds', type=int, default=240)
    args = parser.parse_args()

    payload = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    rows = payload['tasks'] if isinstance(payload, dict) and 'tasks' in payload else payload
    if not isinstance(rows, list):
        raise ValueError('public manifest tasks must be a list')
    tasks = validate_public_manifest(rows)

    if args.checkout_root:
        root = Path(args.checkout_root)
        root.mkdir(parents=True, exist_ok=True)
        cleanup = False
    else:
        root = Path(tempfile.mkdtemp(prefix='nolane-r212-'))
        cleanup = True
    try:
        predictions = [predict_task(task, checkout_root=root, timeout_seconds=args.timeout_seconds) for task in tasks]
    finally:
        if cleanup:
            shutil.rmtree(root, ignore_errors=True)

    out = {
        'schema': 'nolane-r212-real-repo-predictions-v1',
        'tasks': predictions,
    }
    encoded = json.dumps(out, indent=2, sort_keys=True) + '\n'
    Path(args.output).write_text(encoded, encoding='utf-8')


if __name__ == '__main__':
    main()
