from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .types import canonical_digest


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
        return cls(
            str(state['adr_id']), str(state['title']), str(state['context']),
            tuple(str(x) for x in state.get('alternatives', ())), str(state['decision']), str(state['rationale']),
            tuple(str(x) for x in state.get('architecture_refs', ())), tuple(str(x) for x in state.get('evidence_refs', ())),
            str(state['source_agent_id']), ADRStatus(str(state.get('status', ADRStatus.PROPOSED.value))),
            None if state.get('accepted_by') is None else str(state['accepted_by']),
            None if state.get('supersedes') is None else str(state['supersedes']),
            None if state.get('superseded_by') is None else str(state['superseded_by']), str(state.get('digest', '')),
        )


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
        ledger = cls(registry=registry, authority=authority, architecture=architecture)
        ledger._counter = int(state.get('counter', 0))
        for value in state.get('records', ()):
            row = ArchitectureDecision.from_state(value)
            if row.digest != ledger._digest(replace(row, digest='')):
                raise ValueError('ADR digest mismatch')
            ledger._rows[row.adr_id] = row
        if ledger._counter < len(ledger._rows):
            raise ValueError('non-canonical ADR counter')
        return ledger
