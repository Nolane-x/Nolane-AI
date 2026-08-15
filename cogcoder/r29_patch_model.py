from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True, order=True)
class TextEdit:
    """A 1-based, end-exclusive line edit.

    ``start_line == end_line`` inserts before ``start_line``. ``end_line`` may
    equal ``line_count + 1`` so callers can append at EOF.
    """

    path: str
    start_line: int
    end_line: int
    replacement: str

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError('edit path must be non-empty')
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError('invalid edit span')


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    files: Mapping[str, str]

    def __post_init__(self) -> None:
        normalized: dict[str, str] = {}
        for path, content in self.files.items():
            if not path:
                raise ValueError('repository path must be non-empty')
            if not isinstance(content, str):
                raise TypeError('repository file contents must be text')
            normalized[str(path)] = content
        object.__setattr__(self, 'files', MappingProxyType(normalized))


@dataclass(frozen=True, slots=True)
class PatchCandidate:
    candidate_id: str
    edits: tuple[TextEdit, ...]
    parent_candidate_id: str | None = None
    provenance: str = ''
    targeted_nodes: frozenset[str] = frozenset()
    proposal_score: float = 0.0

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError('candidate_id must be non-empty')
        if not self.edits:
            raise ValueError('candidate must contain at least one edit')


def patch_fingerprint(candidate: PatchCandidate) -> str:
    payload = [
        {
            'path': edit.path,
            'start_line': edit.start_line,
            'end_line': edit.end_line,
            'replacement': edit.replacement,
        }
        for edit in sorted(candidate.edits)
    ]
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def apply_candidate(snapshot: RepositorySnapshot, candidate: PatchCandidate) -> RepositorySnapshot:
    files = dict(snapshot.files)
    by_path: dict[str, list[TextEdit]] = {}
    for edit in candidate.edits:
        if edit.path not in files:
            raise KeyError(edit.path)
        by_path.setdefault(edit.path, []).append(edit)

    for path, edits in by_path.items():
        lines = files[path].splitlines(keepends=True)
        max_position = len(lines) + 1
        ordered = sorted(edits, key=lambda item: (item.start_line, item.end_line, item.replacement))
        previous: TextEdit | None = None
        for edit in ordered:
            if edit.start_line > max_position or edit.end_line > max_position:
                raise ValueError('invalid edit span for file length')
            if previous is not None:
                overlaps = edit.start_line < previous.end_line
                same_insertion_point = (
                    edit.start_line == edit.end_line == previous.start_line == previous.end_line
                )
                if overlaps or same_insertion_point:
                    raise ValueError('overlapping edits are not allowed')
            previous = edit

        for edit in reversed(ordered):
            start = edit.start_line - 1
            end = edit.end_line - 1
            lines[start:end] = [edit.replacement] if edit.replacement else []
        files[path] = ''.join(lines)

    return RepositorySnapshot(files)
