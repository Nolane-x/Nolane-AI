from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Mapping


class ClaimMode(str, Enum):
    EXCLUSIVE_WRITE = 'exclusive_write'
    SHARED_READ = 'shared_read'


class ClaimStatus(str, Enum):
    ACTIVE = 'active'
    RELEASED = 'released'
    SUPERSEDED = 'superseded'
    ABORTED = 'aborted'


def _normalize_path(value: str) -> str:
    text = str(value).replace('\\', '/').strip()
    if not text:
        raise ValueError('claim path must be non-empty')
    normalized = str(PurePosixPath(text))
    while normalized.startswith('./'):
        normalized = normalized[2:]
    if normalized.startswith('/') or normalized == '..' or normalized.startswith('../'):
        raise ValueError('claim path must be repository-relative')
    return normalized


def _normalize_symbol(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError('claim symbol must be non-empty')
    return text


@dataclass(frozen=True, slots=True)
class CodeClaim:
    claim_id: str
    agent_id: str
    task_id: str
    file_paths: tuple[str, ...] = ()
    symbol_ids: tuple[str, ...] = ()
    directory_prefixes: tuple[str, ...] = ()
    mode: ClaimMode = ClaimMode.EXCLUSIVE_WRITE
    status: ClaimStatus = ClaimStatus.ACTIVE

    def to_state(self) -> dict[str, Any]:
        return {
            'claim_id': self.claim_id,
            'agent_id': self.agent_id,
            'task_id': self.task_id,
            'file_paths': list(self.file_paths),
            'symbol_ids': list(self.symbol_ids),
            'directory_prefixes': list(self.directory_prefixes),
            'mode': self.mode.value,
            'status': self.status.value,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CodeClaim':
        return cls(
            claim_id=str(state['claim_id']),
            agent_id=str(state['agent_id']),
            task_id=str(state['task_id']),
            file_paths=tuple(_normalize_path(x) for x in state.get('file_paths', ())),
            symbol_ids=tuple(_normalize_symbol(x) for x in state.get('symbol_ids', ())),
            directory_prefixes=tuple(_normalize_path(x).rstrip('/') for x in state.get('directory_prefixes', ())),
            mode=ClaimMode(str(state.get('mode', ClaimMode.EXCLUSIVE_WRITE.value))),
            status=ClaimStatus(str(state.get('status', ClaimStatus.ACTIVE.value))),
        )


class CodeClaimLedger:
    def __init__(self) -> None:
        self._claims: dict[str, CodeClaim] = {}
        self._counter = 0

    def claims(self) -> tuple[CodeClaim, ...]:
        return tuple(self._claims[key] for key in sorted(self._claims))

    def active_claims(self) -> tuple[CodeClaim, ...]:
        return tuple(row for row in self.claims() if row.status is ClaimStatus.ACTIVE)

    def get(self, claim_id: str) -> CodeClaim:
        try:
            return self._claims[str(claim_id)]
        except KeyError as exc:
            raise KeyError(f'unknown code claim: {claim_id}') from exc

    @staticmethod
    def _path_under(path: str, prefix: str) -> bool:
        prefix = prefix.rstrip('/')
        return path == prefix or path.startswith(prefix + '/')

    @classmethod
    def _overlap(cls, left: CodeClaim, right: CodeClaim) -> bool:
        if set(left.symbol_ids) & set(right.symbol_ids):
            return True
        if set(left.file_paths) & set(right.file_paths):
            return True
        for path in left.file_paths:
            if any(cls._path_under(path, prefix) for prefix in right.directory_prefixes):
                return True
        for path in right.file_paths:
            if any(cls._path_under(path, prefix) for prefix in left.directory_prefixes):
                return True
        for a in left.directory_prefixes:
            for b in right.directory_prefixes:
                if cls._path_under(a, b) or cls._path_under(b, a):
                    return True
        return False

    def claim(
        self,
        *,
        agent_id: str,
        task_id: str,
        file_paths: tuple[str, ...] = (),
        symbol_ids: tuple[str, ...] = (),
        directory_prefixes: tuple[str, ...] = (),
        mode: ClaimMode = ClaimMode.EXCLUSIVE_WRITE,
    ) -> CodeClaim:
        agent = str(agent_id).strip()
        task = str(task_id).strip()
        if not agent or not task:
            raise ValueError('code claim requires agent and task')
        files = tuple(sorted(set(_normalize_path(x) for x in file_paths)))
        symbols = tuple(sorted(set(_normalize_symbol(x) for x in symbol_ids)))
        prefixes = tuple(sorted(set(_normalize_path(x).rstrip('/') for x in directory_prefixes)))
        if not files and not symbols and not prefixes:
            raise ValueError('code claim requires at least one source scope')
        candidate = CodeClaim(
            claim_id=f'claim-{self._counter + 1:08d}',
            agent_id=agent,
            task_id=task,
            file_paths=files,
            symbol_ids=symbols,
            directory_prefixes=prefixes,
            mode=ClaimMode(mode),
        )
        if candidate.mode is ClaimMode.EXCLUSIVE_WRITE:
            for active in self.active_claims():
                if active.agent_id == candidate.agent_id:
                    continue
                if active.mode is ClaimMode.EXCLUSIVE_WRITE and self._overlap(active, candidate):
                    raise PermissionError(f'exclusive code scope conflicts with {active.claim_id}')
        self._counter += 1
        self._claims[candidate.claim_id] = candidate
        return candidate

    def release(self, claim_id: str, *, actor_agent_id: str) -> CodeClaim:
        old = self.get(claim_id)
        actor = str(actor_agent_id)
        if old.status is not ClaimStatus.ACTIVE:
            raise ValueError('only active code claims may be released')
        if actor not in {old.agent_id, 'coding.chief', 'nolane.central'}:
            raise PermissionError('claim release requires owner, Coding Chief or Nolane Central')
        row = replace(old, status=ClaimStatus.RELEASED)
        self._claims[row.claim_id] = row
        return row

    def abort(self, claim_id: str, *, actor_agent_id: str) -> CodeClaim:
        old = self.get(claim_id)
        actor = str(actor_agent_id)
        if old.status is not ClaimStatus.ACTIVE:
            raise ValueError('only active code claims may be aborted')
        if actor not in {old.agent_id, 'coding.chief', 'nolane.central'}:
            raise PermissionError('claim abort requires owner, Coding Chief or Nolane Central')
        row = replace(old, status=ClaimStatus.ABORTED)
        self._claims[row.claim_id] = row
        return row

    def covers(
        self,
        *,
        agent_id: str,
        task_id: str,
        file_paths: tuple[str, ...],
        symbol_ids: tuple[str, ...],
    ) -> bool:
        files = tuple(_normalize_path(x) for x in file_paths)
        symbols = tuple(_normalize_symbol(x) for x in symbol_ids)
        active = [
            row for row in self.active_claims()
            if row.agent_id == str(agent_id) and row.task_id == str(task_id)
        ]
        for path in files:
            if not any(path in row.file_paths or any(self._path_under(path, prefix) for prefix in row.directory_prefixes) for row in active):
                return False
        for symbol in symbols:
            if not any(symbol in row.symbol_ids for row in active):
                return False
        return True

    def to_state(self) -> dict[str, Any]:
        return {
            'counter': self._counter,
            'claims': [row.to_state() for row in self.claims()],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CodeClaimLedger':
        ledger = cls()
        for value in state.get('claims', ()):
            row = CodeClaim.from_state(value)
            if row.claim_id in ledger._claims:
                raise ValueError('duplicate code claim id in snapshot')
            ledger._claims[row.claim_id] = row
        ledger._counter = int(state.get('counter', len(ledger._claims)))
        expected_max = 0
        for claim_id in ledger._claims:
            try:
                expected_max = max(expected_max, int(claim_id.rsplit('-', 1)[1]))
            except Exception as exc:
                raise ValueError('non-canonical code claim id') from exc
        if ledger._counter < expected_max:
            raise ValueError('code claim counter is behind claim history')
        active = list(ledger.active_claims())
        for index, left in enumerate(active):
            if left.mode is not ClaimMode.EXCLUSIVE_WRITE:
                continue
            for right in active[index + 1:]:
                if right.mode is ClaimMode.EXCLUSIVE_WRITE and left.agent_id != right.agent_id and ledger._overlap(left, right):
                    raise ValueError('snapshot contains conflicting active exclusive code claims')
        return ledger
