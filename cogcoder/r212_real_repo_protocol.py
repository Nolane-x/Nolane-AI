from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

PUBLIC_PREDICTOR_FIELDS = (
    'instance_id',
    'repo',
    'base_commit',
    'problem_statement',
)

FORBIDDEN_PREDICTOR_FIELDS = frozenset(
    {
        'patch',
        'test_patch',
        'FAIL_TO_PASS',
        'PASS_TO_PASS',
        'pr_description',
        'interface',
        'meta',
        'language',
        'install_config',
        'image_name',
    }
)

_REPO_RE = re.compile(r'^[^/\s]+/[^/\s]+$')
_COMMIT_RE = re.compile(r'^[0-9a-fA-F]{40}$')
_DIFF_HEADER_RE = re.compile(r'^diff --git a/(.+?) b/(.+?)$', re.MULTILINE)
_RENAME_TO_RE = re.compile(r'^rename to (.+)$', re.MULTILINE)


@dataclass(frozen=True)
class PublicRepoTask:
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str

    def __post_init__(self) -> None:
        if not self.instance_id or not isinstance(self.instance_id, str):
            raise ValueError('instance_id must be a non-empty string')
        if not isinstance(self.repo, str) or not _REPO_RE.fullmatch(self.repo):
            raise ValueError('repo must have owner/name shape')
        if not isinstance(self.base_commit, str) or not _COMMIT_RE.fullmatch(self.base_commit):
            raise ValueError('base_commit must be a 40-character git SHA')
        if not isinstance(self.problem_statement, str) or not self.problem_statement.strip():
            raise ValueError('problem_statement must be a non-empty string')

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def redact_dataset_row(row: Mapping[str, Any]) -> dict[str, str]:
    missing = [name for name in PUBLIC_PREDICTOR_FIELDS if name not in row]
    if missing:
        raise ValueError(f"missing required predictor field(s): {', '.join(missing)}")
    task = PublicRepoTask(
        instance_id=str(row['instance_id']),
        repo=str(row['repo']),
        base_commit=str(row['base_commit']),
        problem_statement=str(row['problem_statement']),
    )
    return task.to_dict()


def validate_predictor_payload(payload: Mapping[str, Any]) -> PublicRepoTask:
    forbidden = sorted(set(payload) & FORBIDDEN_PREDICTOR_FIELDS)
    extra = sorted(set(payload) - set(PUBLIC_PREDICTOR_FIELDS))
    if forbidden:
        raise ValueError(f"forbidden predictor field(s): {', '.join(forbidden)}")
    if extra:
        raise ValueError(f"unexpected predictor field(s): {', '.join(extra)}")
    return PublicRepoTask(
        instance_id=str(payload.get('instance_id', '')),
        repo=str(payload.get('repo', '')),
        base_commit=str(payload.get('base_commit', '')),
        problem_statement=str(payload.get('problem_statement', '')),
    )


def extract_gold_patch_files(patch: str) -> tuple[str, ...]:
    if not isinstance(patch, str):
        raise TypeError('patch must be a string')

    rename_targets = iter(_RENAME_TO_RE.findall(patch))
    rename_map: dict[tuple[str, str], str] = {}
    blocks = re.split(r'(?=^diff --git )', patch, flags=re.MULTILINE)
    ordered: list[str] = []
    seen: set[str] = set()

    for block in blocks:
        match = _DIFF_HEADER_RE.search(block)
        if not match:
            continue
        old_path, new_path = match.group(1), match.group(2)
        rename_match = _RENAME_TO_RE.search(block)
        if rename_match:
            path = rename_match.group(1).strip()
        elif re.search(r'^\+\+\+ /dev/null$', block, flags=re.MULTILINE):
            path = old_path
        else:
            path = new_path
        if path not in seen:
            seen.add(path)
            ordered.append(path)

    return tuple(ordered)
