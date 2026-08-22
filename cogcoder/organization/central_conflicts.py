from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping


class ConflictStatus(str, Enum):
    OPEN = 'open'
    RESOLVED = 'resolved'
    ESCALATED = 'escalated'


@dataclass(frozen=True, slots=True)
class ConflictClaim:
    agent_id: str
    statement: str
    evidence_refs: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {'agent_id': self.agent_id, 'statement': self.statement, 'evidence_refs': list(self.evidence_refs)}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ConflictClaim':
        return cls(str(state['agent_id']), str(state['statement']), tuple(str(x) for x in state.get('evidence_refs', ())))


@dataclass(frozen=True, slots=True)
class CentralConflictPacket:
    conflict_id: str
    submitted_by: tuple[str, ...]
    regions: tuple[str, ...]
    object_refs: tuple[str, ...]
    claims: tuple[ConflictClaim, ...]
    severity: int
    affected_refs: tuple[str, ...] = ()
    status: ConflictStatus = ConflictStatus.OPEN
    resolver_agent_id: str | None = None
    decision: str | None = None
    rationale: str | None = None
    resolution_evidence_refs: tuple[str, ...] = ()

    def to_state(self) -> dict[str, Any]:
        return {
            'conflict_id': self.conflict_id,
            'submitted_by': list(self.submitted_by),
            'regions': list(self.regions),
            'object_refs': list(self.object_refs),
            'claims': [x.to_state() for x in self.claims],
            'severity': self.severity,
            'affected_refs': list(self.affected_refs),
            'status': self.status.value,
            'resolver_agent_id': self.resolver_agent_id,
            'decision': self.decision,
            'rationale': self.rationale,
            'resolution_evidence_refs': list(self.resolution_evidence_refs),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CentralConflictPacket':
        return cls(
            conflict_id=str(state['conflict_id']),
            submitted_by=tuple(str(x) for x in state.get('submitted_by', ())),
            regions=tuple(str(x) for x in state.get('regions', ())),
            object_refs=tuple(str(x) for x in state.get('object_refs', ())),
            claims=tuple(ConflictClaim.from_state(x) for x in state.get('claims', ())),
            severity=int(state['severity']),
            affected_refs=tuple(str(x) for x in state.get('affected_refs', ())),
            status=ConflictStatus(str(state.get('status', ConflictStatus.OPEN.value))),
            resolver_agent_id=None if state.get('resolver_agent_id') is None else str(state['resolver_agent_id']),
            decision=None if state.get('decision') is None else str(state['decision']),
            rationale=None if state.get('rationale') is None else str(state['rationale']),
            resolution_evidence_refs=tuple(str(x) for x in state.get('resolution_evidence_refs', ())),
        )


class CentralConflictRegistry:
    def __init__(self) -> None:
        self._rows: dict[str, CentralConflictPacket] = {}
        self._counter = 0

    @staticmethod
    def _severity(value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError('conflict severity must be an integer from 0 to 100')
        return value

    @staticmethod
    def _claim(raw: tuple[str, str, tuple[str, ...]]) -> ConflictClaim:
        agent_id, statement, refs = raw
        agent_id = str(agent_id).strip()
        statement = str(statement).strip()
        evidence = tuple(str(x).strip() for x in refs if str(x).strip())
        if not agent_id or not statement or not evidence:
            raise ValueError('each conflict claim requires agent, statement and evidence')
        return ConflictClaim(agent_id, statement, evidence)

    def open(self, *, submitted_by: tuple[str, ...], regions: tuple[str, ...], object_refs: tuple[str, ...],
             claims: tuple[tuple[str, str, tuple[str, ...]], ...], severity: int,
             affected_refs: tuple[str, ...] = ()) -> CentralConflictPacket:
        submitters = tuple(dict.fromkeys(str(x).strip() for x in submitted_by if str(x).strip()))
        region_rows = tuple(dict.fromkeys(str(x).strip() for x in regions if str(x).strip()))
        objects = tuple(dict.fromkeys(str(x).strip() for x in object_refs if str(x).strip()))
        claim_rows = tuple(self._claim(x) for x in claims)
        if len(submitters) < 2 or len(region_rows) < 2 or len(claim_rows) < 2:
            raise ValueError('cross-region conflict requires at least two submitters, regions and claims')
        if not objects:
            raise ValueError('conflict requires at least one object reference')
        severity = self._severity(severity)
        counter = self._counter + 1
        packet = CentralConflictPacket(
            conflict_id=f'conflict-{counter:08d}', submitted_by=submitters, regions=region_rows,
            object_refs=objects, claims=claim_rows, severity=severity,
            affected_refs=tuple(str(x) for x in affected_refs if str(x).strip()),
        )
        self._counter = counter
        self._rows[packet.conflict_id] = packet
        return packet

    def get(self, conflict_id: str) -> CentralConflictPacket:
        try:
            return self._rows[str(conflict_id)]
        except KeyError as exc:
            raise KeyError(f'unknown conflict id: {conflict_id}') from exc

    def resolve(self, conflict_id: str, *, resolver_agent_id: str, decision: str, rationale: str,
                evidence_refs: tuple[str, ...]) -> CentralConflictPacket:
        old = self.get(conflict_id)
        if old.status is not ConflictStatus.OPEN:
            raise ValueError('only an open conflict may be resolved')
        resolver = str(resolver_agent_id).strip()
        decision = str(decision).strip()
        rationale = str(rationale).strip()
        evidence = tuple(str(x).strip() for x in evidence_refs if str(x).strip())
        if not resolver or not decision or not rationale or not evidence:
            raise ValueError('conflict resolution requires resolver, decision, rationale and evidence')
        row = replace(old, status=ConflictStatus.RESOLVED, resolver_agent_id=resolver,
                      decision=decision, rationale=rationale, resolution_evidence_refs=evidence)
        self._rows[row.conflict_id] = row
        return row

    def escalate(self, conflict_id: str, *, resolver_agent_id: str, rationale: str,
                 evidence_refs: tuple[str, ...]) -> CentralConflictPacket:
        old = self.get(conflict_id)
        evidence = tuple(str(x).strip() for x in evidence_refs if str(x).strip())
        if old.status is not ConflictStatus.OPEN or not str(resolver_agent_id).strip() or not str(rationale).strip() or not evidence:
            raise ValueError('conflict escalation requires an open conflict, resolver, rationale and evidence')
        row = replace(old, status=ConflictStatus.ESCALATED, resolver_agent_id=str(resolver_agent_id),
                      rationale=str(rationale), resolution_evidence_refs=evidence)
        self._rows[row.conflict_id] = row
        return row

    def packets(self) -> tuple[CentralConflictPacket, ...]:
        return tuple(self._rows[k] for k in sorted(self._rows))

    def to_state(self) -> dict[str, Any]:
        return {'conflicts': [x.to_state() for x in self.packets()], 'counter': self._counter}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CentralConflictRegistry':
        registry = cls()
        rows = [CentralConflictPacket.from_state(x) for x in state.get('conflicts', ())]
        for expected, row in enumerate(rows, start=1):
            if row.conflict_id != f'conflict-{expected:08d}':
                raise ValueError('conflict ids are not canonical')
            registry._severity(row.severity)
            if len(row.claims) < 2:
                raise ValueError('restored conflict requires competing claims')
            registry._rows[row.conflict_id] = row
        registry._counter = int(state.get('counter', len(rows)))
        if registry._counter != len(rows):
            raise ValueError('conflict counter is not canonical')
        return registry
