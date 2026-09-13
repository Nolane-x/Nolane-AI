from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .types import canonical_digest


def _record(state: object, keys: tuple[str, ...], label: str) -> dict[str, Any]:
    if type(state) is not dict or set(state) != set(keys):
        raise ValueError(f'{label} must use canonical serialized state')
    return state


def _list(value: object, label: str) -> list[Any]:
    if type(value) is not list:
        raise ValueError(f'{label} must use canonical serialized state')
    return value


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f'{label} must be an exact non-empty string')
    return value


def _nullable_string(value: object, label: str) -> str | None:
    return None if value is None else _string(value, label)


def _strings(value: object, label: str) -> tuple[str, ...]:
    return tuple(_string(item, label) for item in _list(value, label))


class ADRStatus(str, Enum):
    PROPOSED = 'proposed'
    ACCEPTED = 'accepted'
    SUPERSEDED = 'superseded'
    REJECTED = 'rejected'


@dataclass(frozen=True, slots=True)
class ArchitectureDecision:
    adr_id: str
    title: str
    context: str
    alternatives: tuple[str, ...]
    decision: str
    rationale: str
    architecture_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    source_agent_id: str
    status: ADRStatus = ADRStatus.PROPOSED
    accepted_by: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    digest: str = ''

    def to_state(self) -> dict[str, Any]:
        return {
            'adr_id': self.adr_id, 'title': self.title, 'context': self.context,
            'alternatives': list(self.alternatives), 'decision': self.decision, 'rationale': self.rationale,
            'architecture_refs': list(self.architecture_refs), 'evidence_refs': list(self.evidence_refs),
            'source_agent_id': self.source_agent_id, 'status': self.status.value, 'accepted_by': self.accepted_by,
            'supersedes': self.supersedes, 'superseded_by': self.superseded_by, 'digest': self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ArchitectureDecision':
        state = _record(state, (
            'adr_id', 'title', 'context', 'alternatives', 'decision', 'rationale',
            'architecture_refs', 'evidence_refs', 'source_agent_id', 'status',
            'accepted_by', 'supersedes', 'superseded_by', 'digest',
        ), 'ADR record')
        row = cls(
            _string(state['adr_id'], 'ADR identity'),
            _string(state['title'], 'ADR title'),
            _string(state['context'], 'ADR context'),
            _strings(state['alternatives'], 'ADR alternative'),
            _string(state['decision'], 'ADR decision'),
            _string(state['rationale'], 'ADR rationale'),
            _strings(state['architecture_refs'], 'ADR architecture reference'),
            _strings(state['evidence_refs'], 'ADR evidence reference'),
            _string(state['source_agent_id'], 'ADR source agent'),
            ADRStatus(_string(state['status'], 'ADR status')),
            _nullable_string(state['accepted_by'], 'ADR accepting agent'),
            _nullable_string(state['supersedes'], 'ADR supersedes reference'),
            _nullable_string(state['superseded_by'], 'ADR superseded-by reference'),
            _string(state['digest'], 'ADR digest'),
        )
        if len(row.alternatives) < 2 or not row.evidence_refs:
            raise ValueError('ADR restore requires at least two alternatives and evidence')
        if row.status is ADRStatus.PROPOSED and any(
            value is not None for value in (row.accepted_by, row.supersedes, row.superseded_by)
        ):
            raise ValueError('proposed ADR cannot carry acceptance or supersession authority')
        if row.status is ADRStatus.ACCEPTED and (row.accepted_by is None or row.superseded_by is not None):
            raise ValueError('accepted ADR requires current acceptance authority')
        if row.status is ADRStatus.SUPERSEDED and (row.accepted_by is None or row.superseded_by is None):
            raise ValueError('superseded ADR requires acceptance and supersession provenance')
        return row


class ADRDecisionLedger:
    def __init__(self, *, registry: Any, authority: Any, architecture: Any) -> None:
        self.registry, self.authority, self.architecture = registry, authority, architecture
        self._rows: dict[str, ArchitectureDecision] = {}
        self._counter = 0

    def _digest(self, row: ArchitectureDecision) -> str:
        state = row.to_state(); state.pop('digest', None)
        return canonical_digest(state)

    def propose(self, *, source_agent_id: str, title: str, context: str, alternatives: tuple[str, ...], decision: str, rationale: str, architecture_refs: tuple[str, ...], evidence_refs: tuple[str, ...]) -> ArchitectureDecision:
        self.registry.get(source_agent_id)
        if not all(str(x).strip() for x in (title, context, decision, rationale)) or len(alternatives) < 2 or not evidence_refs:
            raise ValueError('ADR proposal requires context, at least two alternatives, decision, rationale and evidence')
        for ref in architecture_refs:
            if not self.architecture.graph.contains_ref(ref):
                raise ValueError(f'ADR references unknown architecture object: {ref}')
        self._counter += 1
        row = ArchitectureDecision(
            adr_id=f'ADR-{self._counter:08d}', title=str(title), context=str(context),
            alternatives=tuple(str(x) for x in alternatives), decision=str(decision), rationale=str(rationale),
            architecture_refs=tuple(str(x) for x in architecture_refs), evidence_refs=tuple(str(x) for x in evidence_refs),
            source_agent_id=str(source_agent_id),
        )
        row = replace(row, digest=self._digest(row))
        self._rows[row.adr_id] = row
        return row

    def get(self, adr_id: str) -> ArchitectureDecision:
        try:
            return self._rows[str(adr_id)]
        except KeyError as exc:
            raise KeyError(f'unknown ADR: {adr_id}') from exc

    def records(self) -> tuple[ArchitectureDecision, ...]:
        return tuple(self._rows[k] for k in sorted(self._rows))

    def accept(self, adr_id: str, *, actor_agent_id: str, evidence_refs: tuple[str, ...], supersedes: str | None = None) -> ArchitectureDecision:
        self.registry.get(actor_agent_id)
        self.authority.require_write(actor_agent_id, 'architecture-graph')
        if not evidence_refs:
            raise ValueError('ADR acceptance requires evidence')
        row = self.get(adr_id)
        if row.status is not ADRStatus.PROPOSED:
            raise ValueError('only proposed ADR may be accepted')
        if supersedes is not None:
            old = self.get(supersedes)
            if old.status is not ADRStatus.ACCEPTED:
                raise ValueError('superseded ADR must currently be accepted')
            old = replace(old, status=ADRStatus.SUPERSEDED, superseded_by=row.adr_id)
            old = replace(old, digest=self._digest(old))
            self._rows[old.adr_id] = old
        accepted = replace(
            row, status=ADRStatus.ACCEPTED, accepted_by=str(actor_agent_id),
            supersedes=None if supersedes is None else str(supersedes),
            evidence_refs=tuple(dict.fromkeys(row.evidence_refs + tuple(str(x) for x in evidence_refs))),
        )
        accepted = replace(accepted, digest=self._digest(accepted))
        self._rows[accepted.adr_id] = accepted
        return accepted

    def to_state(self) -> dict[str, Any]:
        return {'counter': self._counter, 'records': [x.to_state() for x in self.records()]}

    @classmethod
    def from_state(cls, *, registry: Any, authority: Any, architecture: Any, state: Mapping[str, Any]) -> 'ADRDecisionLedger':
        state = _record(state, ('counter', 'records'), 'ADR ledger')
        counter = state['counter']
        if type(counter) is not int or counter < 0:
            raise ValueError('non-canonical ADR counter')
        raw_records = _list(state['records'], 'ADR records')
        ledger = cls(registry=registry, authority=authority, architecture=architecture)
        seen: set[str] = set()
        ids: list[str] = []
        for value in raw_records:
            row = ArchitectureDecision.from_state(value)
            if row.adr_id in seen:
                raise ValueError(f'duplicate ADR identity: {row.adr_id}')
            seen.add(row.adr_id); ids.append(row.adr_id)
            if row.digest != ledger._digest(row):
                raise ValueError('ADR digest mismatch')
            try:
                registry.get(row.source_agent_id)
                if row.accepted_by is not None:
                    registry.get(row.accepted_by)
            except KeyError as exc:
                raise ValueError(f'ADR references unknown agent: {row.adr_id}') from exc
            for ref in row.architecture_refs:
                if not architecture.graph.contains_ref(ref):
                    raise ValueError(f'ADR references unknown architecture object: {ref}')
            ledger._rows[row.adr_id] = row
        if ids != sorted(ids):
            raise ValueError('ADR records must use canonical serialized state order')
        if ids != [f'ADR-{index:08d}' for index in range(1, len(ids) + 1)]:
            raise ValueError('non-canonical ADR identity sequence')
        if counter != len(ids):
            raise ValueError('non-canonical ADR counter')
        ledger._counter = counter
        for row in ledger.records():
            if row.supersedes is not None:
                previous = ledger._rows.get(row.supersedes)
                if (
                    row.status not in (ADRStatus.ACCEPTED, ADRStatus.SUPERSEDED)
                    or previous is None or previous.status is not ADRStatus.SUPERSEDED
                    or previous.superseded_by != row.adr_id or previous.adr_id >= row.adr_id
                ):
                    raise ValueError('ADR supersession provenance is incoherent')
            if row.superseded_by is not None:
                successor = ledger._rows.get(row.superseded_by)
                if (
                    row.status is not ADRStatus.SUPERSEDED or successor is None
                    or successor.status not in (ADRStatus.ACCEPTED, ADRStatus.SUPERSEDED)
                    or successor.supersedes != row.adr_id or successor.adr_id <= row.adr_id
                ):
                    raise ValueError('ADR supersession provenance is incoherent')
        return ledger
