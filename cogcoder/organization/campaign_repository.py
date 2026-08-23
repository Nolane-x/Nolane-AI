from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .types import canonical_digest


_MOVABLE_REVISIONS = {'main', 'master', 'head', 'latest', 'tip', 'trunk'}


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    snapshot_id: str
    repository: str
    revision: str
    language: str
    toolchain_digest: str
    test_command_digest: str
    contamination_policy_digest: str
    source_metadata: Mapping[str, Any]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'snapshot_id': self.snapshot_id,
            'repository': self.repository,
            'revision': self.revision,
            'language': self.language,
            'toolchain_digest': self.toolchain_digest,
            'test_command_digest': self.test_command_digest,
            'contamination_policy_digest': self.contamination_policy_digest,
            'source_metadata': dict(sorted((str(k), v) for k, v in self.source_metadata.items())),
        }

    def registration_kwargs(self) -> dict[str, Any]:
        return {
            'snapshot_id': self.snapshot_id, 'repository': self.repository, 'revision': self.revision,
            'language': self.language, 'toolchain_digest': self.toolchain_digest,
            'test_command_digest': self.test_command_digest,
            'contamination_policy_digest': self.contamination_policy_digest,
            'source_metadata': dict(self.source_metadata),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'RepositorySnapshot':
        row = cls(
            snapshot_id=str(state['snapshot_id']), repository=str(state['repository']),
            revision=str(state['revision']), language=str(state['language']),
            toolchain_digest=str(state['toolchain_digest']), test_command_digest=str(state['test_command_digest']),
            contamination_policy_digest=str(state['contamination_policy_digest']),
            source_metadata=dict(state.get('source_metadata', {})), digest=str(state['digest']),
        )
        _validate_snapshot(row)
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('repository snapshot digest mismatch')
        return row


def _validate_snapshot(row: RepositorySnapshot) -> None:
    for value, label in (
        (row.snapshot_id, 'snapshot id'), (row.repository, 'repository'), (row.revision, 'revision'),
        (row.language, 'language'), (row.toolchain_digest, 'toolchain digest'),
        (row.test_command_digest, 'test command digest'),
        (row.contamination_policy_digest, 'contamination policy digest'),
    ):
        if not str(value).strip():
            raise ValueError(f'{label} must be explicit')
    if row.revision.strip().lower() in _MOVABLE_REVISIONS:
        raise ValueError('frozen repository snapshot requires an immutable revision, not a movable ref')
    if len(row.revision.strip()) < 12:
        raise ValueError('frozen repository revision is too short to be treated as immutable identity')


class RepositorySnapshotRegistry:
    def __init__(self, snapshots: tuple[RepositorySnapshot, ...] = ()) -> None:
        self._rows: dict[str, RepositorySnapshot] = {}
        for row in snapshots:
            _validate_snapshot(row)
            if row.snapshot_id in self._rows:
                raise ValueError('duplicate repository snapshot id')
            self._rows[row.snapshot_id] = row

    def register(self, **kwargs: Any) -> RepositorySnapshot:
        row0 = RepositorySnapshot(
            snapshot_id=str(kwargs['snapshot_id']), repository=str(kwargs['repository']),
            revision=str(kwargs['revision']), language=str(kwargs['language']),
            toolchain_digest=str(kwargs['toolchain_digest']), test_command_digest=str(kwargs['test_command_digest']),
            contamination_policy_digest=str(kwargs['contamination_policy_digest']),
            source_metadata=dict(kwargs.get('source_metadata', {})), digest='',
        )
        _validate_snapshot(row0)
        row = RepositorySnapshot(
            snapshot_id=row0.snapshot_id, repository=row0.repository, revision=row0.revision,
            language=row0.language, toolchain_digest=row0.toolchain_digest,
            test_command_digest=row0.test_command_digest,
            contamination_policy_digest=row0.contamination_policy_digest,
            source_metadata=row0.source_metadata, digest=canonical_digest(row0.payload()),
        )
        existing = self._rows.get(row.snapshot_id)
        if existing is not None:
            if existing == row:
                return existing
            raise ValueError('repository snapshot id cannot be rebound')
        self._rows[row.snapshot_id] = row
        return row

    def get(self, snapshot_id: str) -> RepositorySnapshot:
        try:
            return self._rows[str(snapshot_id)]
        except KeyError as exc:
            raise KeyError(f'unknown repository snapshot: {snapshot_id}') from exc

    def snapshots(self) -> tuple[RepositorySnapshot, ...]:
        return tuple(self._rows[key] for key in sorted(self._rows))

    def to_state(self) -> dict[str, Any]:
        return {'snapshots': [row.to_state() for row in self.snapshots()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'RepositorySnapshotRegistry':
        return cls(tuple(RepositorySnapshot.from_state(x) for x in state.get('snapshots', ())))
