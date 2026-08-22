from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .types import canonical_digest


class ScratchDisposition(str, Enum):
    DESTROY = 'destroy'
    ARCHIVE_QUARANTINE = 'archive_quarantine'


@dataclass(frozen=True, slots=True)
class ScratchEntry:
    entry_id: str
    sequence: int
    ephemeral_id: str
    team_id: str
    content: str
    content_digest: str
    quarantined: bool
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'entry_id': self.entry_id,
            'sequence': self.sequence,
            'ephemeral_id': self.ephemeral_id,
            'team_id': self.team_id,
            'content': self.content,
            'content_digest': self.content_digest,
            'quarantined': self.quarantined,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ScratchEntry':
        row = cls(
            entry_id=str(state['entry_id']), sequence=int(state['sequence']),
            ephemeral_id=str(state['ephemeral_id']), team_id=str(state['team_id']),
            content=str(state['content']), content_digest=str(state['content_digest']),
            quarantined=bool(state.get('quarantined', False)), digest=str(state['digest']),
        )
        if row.sequence <= 0 or canonical_digest(row.content) != row.content_digest:
            raise ValueError('Foundry scratch content digest mismatch')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('Foundry scratch entry digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ScratchTombstone:
    entry_id: str
    sequence: int
    ephemeral_id: str
    team_id: str
    content_digest: str
    disposition: ScratchDisposition
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'entry_id': self.entry_id,
            'sequence': self.sequence,
            'ephemeral_id': self.ephemeral_id,
            'team_id': self.team_id,
            'content_digest': self.content_digest,
            'disposition': self.disposition.value,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ScratchTombstone':
        row = cls(
            entry_id=str(state['entry_id']), sequence=int(state['sequence']),
            ephemeral_id=str(state['ephemeral_id']), team_id=str(state['team_id']),
            content_digest=str(state['content_digest']),
            disposition=ScratchDisposition(str(state['disposition'])), digest=str(state['digest']),
        )
        if row.sequence <= 0 or not row.content_digest.strip():
            raise ValueError('invalid Foundry scratch tombstone')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('Foundry scratch tombstone digest mismatch')
        return row


def _signed_entry(**kwargs: Any) -> ScratchEntry:
    temp = ScratchEntry(digest='', **kwargs)
    return replace(temp, digest=canonical_digest(temp.payload()))


def _signed_tombstone(**kwargs: Any) -> ScratchTombstone:
    temp = ScratchTombstone(digest='', **kwargs)
    return replace(temp, digest=canonical_digest(temp.payload()))


class EphemeralScratchVault:
    def __init__(
        self,
        *,
        registrations: Mapping[str, str] | None = None,
        entries: tuple[ScratchEntry, ...] = (),
        tombstones: tuple[ScratchTombstone, ...] = (),
        retired: tuple[str, ...] = (),
        counter: int = 0,
    ) -> None:
        self._teams = {str(key): str(value) for key, value in (registrations or {}).items()}
        self._entries: dict[str, ScratchEntry] = {}
        self._by_ephemeral: dict[str, list[str]] = {key: [] for key in self._teams}
        for row in entries:
            if row.ephemeral_id not in self._teams or self._teams[row.ephemeral_id] != row.team_id:
                raise ValueError('Foundry scratch entry registration mismatch')
            if row.entry_id in self._entries:
                raise ValueError('duplicate Foundry scratch entry')
            self._entries[row.entry_id] = row
            self._by_ephemeral.setdefault(row.ephemeral_id, []).append(row.entry_id)
        self._tombstones: dict[str, ScratchTombstone] = {}
        for row in tombstones:
            if row.ephemeral_id not in self._teams or self._teams[row.ephemeral_id] != row.team_id:
                raise ValueError('Foundry scratch tombstone registration mismatch')
            if row.entry_id in self._tombstones:
                raise ValueError('duplicate Foundry scratch tombstone')
            if row.entry_id in self._entries and row.disposition is ScratchDisposition.DESTROY:
                raise ValueError('destroyed Foundry scratch cannot retain plaintext entry')
            self._tombstones[row.entry_id] = row
        self._retired = {str(value) for value in retired}
        if not self._retired.issubset(self._teams):
            raise ValueError('Foundry scratch retired set references unknown identity')
        self._counter = int(counter)
        max_sequence = max([0] + [row.sequence for row in entries] + [row.sequence for row in tombstones])
        if self._counter < max_sequence:
            raise ValueError('Foundry scratch counter is not canonical')

    def register(self, ephemeral_id: str, *, team_id: str) -> None:
        eid, team = str(ephemeral_id), str(team_id)
        if not eid.strip() or not team.strip():
            raise ValueError('Foundry scratch registration requires identity and team')
        existing = self._teams.get(eid)
        if existing is not None:
            if existing != team:
                raise ValueError('Foundry scratch identity cannot change team')
            return
        self._teams[eid] = team
        self._by_ephemeral[eid] = []

    def _require_owner(self, ephemeral_id: str, actor_ephemeral_id: str) -> str:
        eid = str(ephemeral_id)
        if eid not in self._teams:
            raise KeyError(f'unknown Foundry scratch identity: {ephemeral_id}')
        if str(actor_ephemeral_id) != eid:
            raise PermissionError('Foundry scratch is private to the exact ephemeral identity')
        if eid in self._retired:
            raise PermissionError('retired Foundry worker cannot access scratch')
        return eid

    def write(self, ephemeral_id: str, text: str, *, actor_ephemeral_id: str) -> ScratchEntry:
        eid = self._require_owner(ephemeral_id, actor_ephemeral_id)
        content = str(text)
        if not content.strip():
            raise ValueError('Foundry scratch content must be non-empty')
        self._counter += 1
        entry_id = f'foundry-scratch-{self._counter:08d}'
        row = _signed_entry(
            entry_id=entry_id, sequence=self._counter, ephemeral_id=eid,
            team_id=self._teams[eid], content=content,
            content_digest=canonical_digest(content), quarantined=False,
        )
        self._entries[row.entry_id] = row
        self._by_ephemeral[eid].append(row.entry_id)
        return row

    def read(self, ephemeral_id: str, *, actor_ephemeral_id: str) -> tuple[ScratchEntry, ...]:
        eid = self._require_owner(ephemeral_id, actor_ephemeral_id)
        return tuple(
            self._entries[entry_id]
            for entry_id in self._by_ephemeral.get(eid, ())
            if entry_id in self._entries and not self._entries[entry_id].quarantined
        )

    def retire(self, ephemeral_id: str, disposition: ScratchDisposition) -> tuple[ScratchTombstone, ...]:
        eid = str(ephemeral_id)
        if eid not in self._teams:
            raise KeyError(f'unknown Foundry scratch identity: {ephemeral_id}')
        disposition = ScratchDisposition(disposition)
        existing = self.destroyed_tombstones(eid) if disposition is ScratchDisposition.DESTROY else tuple(
            self._tombstones[key] for key in sorted(self._tombstones)
            if self._tombstones[key].ephemeral_id == eid and self._tombstones[key].disposition is disposition
        )
        if eid in self._retired and existing:
            return existing
        produced: list[ScratchTombstone] = []
        for entry_id in list(self._by_ephemeral.get(eid, ())):
            entry = self._entries.get(entry_id)
            if entry is None:
                continue
            tombstone = _signed_tombstone(
                entry_id=entry.entry_id, sequence=entry.sequence, ephemeral_id=entry.ephemeral_id,
                team_id=entry.team_id, content_digest=entry.content_digest, disposition=disposition,
            )
            self._tombstones[entry.entry_id] = tombstone
            produced.append(tombstone)
            if disposition is ScratchDisposition.DESTROY:
                self._entries.pop(entry.entry_id, None)
            else:
                self._entries[entry.entry_id] = _signed_entry(
                    entry_id=entry.entry_id, sequence=entry.sequence, ephemeral_id=entry.ephemeral_id,
                    team_id=entry.team_id, content=entry.content,
                    content_digest=entry.content_digest, quarantined=True,
                )
        self._retired.add(eid)
        return tuple(produced)

    def archived_entries(self, ephemeral_id: str) -> tuple[ScratchEntry, ...]:
        eid = str(ephemeral_id)
        return tuple(
            row for row in sorted(self._entries.values(), key=lambda value: value.sequence)
            if row.ephemeral_id == eid and row.quarantined
        )

    def destroyed_tombstones(self, ephemeral_id: str) -> tuple[ScratchTombstone, ...]:
        eid = str(ephemeral_id)
        return tuple(
            row for row in sorted(self._tombstones.values(), key=lambda value: value.sequence)
            if row.ephemeral_id == eid and row.disposition is ScratchDisposition.DESTROY
        )

    def to_state(self) -> dict[str, Any]:
        return {
            'registrations': dict(sorted(self._teams.items())),
            'entries': [row.to_state() for row in sorted(self._entries.values(), key=lambda value: value.sequence)],
            'tombstones': [row.to_state() for row in sorted(self._tombstones.values(), key=lambda value: value.sequence)],
            'retired': sorted(self._retired),
            'counter': self._counter,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'EphemeralScratchVault':
        return cls(
            registrations=state.get('registrations', {}),
            entries=tuple(ScratchEntry.from_state(x) for x in state.get('entries', ())),
            tombstones=tuple(ScratchTombstone.from_state(x) for x in state.get('tombstones', ())),
            retired=tuple(str(x) for x in state.get('retired', ())),
            counter=int(state.get('counter', 0)),
        )
