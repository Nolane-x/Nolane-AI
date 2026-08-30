from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.fabric import MemoryFabric, MemoryStatus
from nolane.organization.events import EventLedger
from nolane.organization.identity import AgentRegistry


COMPONENT_ID = "external.memory.lifecycle"
COMPONENT_VERSION = "0.0.2"
MIGRATED_FROM = "cogcoder.organization.memory_lifecycle"


_ALLOWED_MEMORY_TRANSITIONS: dict[MemoryStatus, frozenset[MemoryStatus]] = {
    MemoryStatus.ACTIVE: frozenset({
        MemoryStatus.QUARANTINED,
        MemoryStatus.STALE,
        MemoryStatus.SUPERSEDED,
        MemoryStatus.CONTRADICTED,
        MemoryStatus.ARCHIVED,
    }),
    MemoryStatus.QUARANTINED: frozenset({
        MemoryStatus.ACTIVE,
        MemoryStatus.CONTRADICTED,
        MemoryStatus.ARCHIVED,
    }),
    MemoryStatus.STALE: frozenset({
        MemoryStatus.ACTIVE,
        MemoryStatus.SUPERSEDED,
        MemoryStatus.CONTRADICTED,
        MemoryStatus.ARCHIVED,
    }),
    MemoryStatus.CONTRADICTED: frozenset({
        MemoryStatus.ACTIVE,
        MemoryStatus.SUPERSEDED,
        MemoryStatus.ARCHIVED,
    }),
    MemoryStatus.SUPERSEDED: frozenset({MemoryStatus.ARCHIVED}),
    MemoryStatus.ARCHIVED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class MemoryLifecycleReceipt:
    receipt_id: str
    memory_id: str
    previous_status: MemoryStatus
    new_status: MemoryStatus
    actor_agent_id: str
    reason: str
    evidence_refs: tuple[str, ...]
    correction_ref: str | None
    event_anchor_id: str | None
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'receipt_id': self.receipt_id,
            'memory_id': self.memory_id,
            'previous_status': self.previous_status.value,
            'new_status': self.new_status.value,
            'actor_agent_id': self.actor_agent_id,
            'reason': self.reason,
            'evidence_refs': list(self.evidence_refs),
            'correction_ref': self.correction_ref,
            'event_anchor_id': self.event_anchor_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'MemoryLifecycleReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']),
            memory_id=str(state['memory_id']),
            previous_status=MemoryStatus(str(state['previous_status'])),
            new_status=MemoryStatus(str(state['new_status'])),
            actor_agent_id=str(state['actor_agent_id']),
            reason=str(state['reason']),
            evidence_refs=tuple(str(value) for value in state.get('evidence_refs', ())),
            correction_ref=None if state.get('correction_ref') is None else str(state['correction_ref']),
            event_anchor_id=None if state.get('event_anchor_id') is None else str(state['event_anchor_id']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('memory lifecycle receipt digest mismatch')
        return row


class MemoryLifecycleLedger:
    REGION = 'memory-context-knowledge'

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        memory: MemoryFabric,
        events: EventLedger,
        receipts: tuple[MemoryLifecycleReceipt, ...] = (),
        counter: int = 0,
    ) -> None:
        self.registry = registry
        self.memory = memory
        self.events = events
        self._receipts = list(receipts)
        self._counter = int(counter)

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def receipts(self) -> tuple[MemoryLifecycleReceipt, ...]:
        return tuple(self._receipts)

    def receipts_for(self, memory_id: str) -> tuple[MemoryLifecycleReceipt, ...]:
        self.memory.get(memory_id)
        return tuple(row for row in self._receipts if row.memory_id == str(memory_id))

    @staticmethod
    def _require_allowed_transition(previous: MemoryStatus, target: MemoryStatus) -> None:
        allowed = _ALLOWED_MEMORY_TRANSITIONS[MemoryStatus(previous)]
        if MemoryStatus(target) not in allowed:
            raise PermissionError(
                f'forbidden memory lifecycle transition: {MemoryStatus(previous).value} -> {MemoryStatus(target).value}'
            )

    def _authorize(self, actor_agent_id: str, new_status: MemoryStatus) -> None:
        actor = self.registry.get(actor_agent_id)
        if actor.region != self.REGION:
            raise PermissionError('privileged memory lifecycle transitions require a Memory/Context identity')
        if new_status is MemoryStatus.ACTIVE and actor.agent_id != 'memory.chief':
            raise PermissionError('reactivating governed memory requires Memory Chief authority')

    def transition(
        self,
        memory_id: str,
        *,
        actor_agent_id: str,
        new_status: MemoryStatus,
        reason: str,
        evidence_refs: tuple[str, ...],
        correction_ref: str | None = None,
    ) -> MemoryLifecycleReceipt:
        old = self.memory.get(memory_id)
        target = MemoryStatus(new_status)
        self._authorize(actor_agent_id, target)
        if old.status is target:
            raise ValueError('memory lifecycle transition must change status')
        self._require_allowed_transition(old.status, target)
        if not str(reason).strip() or not evidence_refs:
            raise ValueError('memory lifecycle transition requires explicit reason and evidence')
        if target is MemoryStatus.ACTIVE and not (correction_ref and str(correction_ref).strip()):
            raise ValueError('reactivation requires an explicit corrective reference')
        if target is not MemoryStatus.ACTIVE and correction_ref is not None:
            correction_ref = str(correction_ref)

        self._counter += 1
        receipt_id = f'memory-lifecycle-{self._counter:08d}'
        anchor = self.events.latest_event_id()
        payload = {
            'receipt_id': receipt_id,
            'memory_id': old.memory_id,
            'previous_status': old.status.value,
            'new_status': target.value,
            'actor_agent_id': str(actor_agent_id),
            'reason': str(reason),
            'evidence_refs': [str(value) for value in evidence_refs],
            'correction_ref': None if correction_ref is None else str(correction_ref),
            'event_anchor_id': anchor,
        }
        receipt = MemoryLifecycleReceipt(
            receipt_id=receipt_id,
            memory_id=old.memory_id,
            previous_status=old.status,
            new_status=target,
            actor_agent_id=str(actor_agent_id),
            reason=str(reason),
            evidence_refs=tuple(str(value) for value in evidence_refs),
            correction_ref=None if correction_ref is None else str(correction_ref),
            event_anchor_id=anchor,
            digest=canonical_digest(payload),
        )
        self.memory.set_status(old.memory_id, target, reason=str(reason))
        self._receipts.append(receipt)
        return receipt

    def to_state(self) -> dict[str, Any]:
        return {
            'receipts': [row.to_state() for row in self._receipts],
            'counter': self._counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        memory: MemoryFabric,
        events: EventLedger,
        state: Mapping[str, Any],
    ) -> 'MemoryLifecycleLedger':
        receipts = tuple(MemoryLifecycleReceipt.from_state(row) for row in state.get('receipts', ()))
        result = cls(
            registry=registry,
            memory=memory,
            events=events,
            receipts=receipts,
            counter=int(state.get('counter', len(receipts))),
        )
        for row in receipts:
            registry.get(row.actor_agent_id)
            memory.get(row.memory_id)
            if row.event_anchor_id is not None:
                events.get(row.event_anchor_id)
        latest_by_memory: dict[str, MemoryLifecycleReceipt] = {}
        for row in receipts:
            latest_by_memory[row.memory_id] = row
        for memory_id, row in latest_by_memory.items():
            if memory.get(memory_id).status is not row.new_status:
                raise ValueError('restored memory status disagrees with lifecycle history')
        return result


class MemoryRelationKind(str, Enum):
    SUPPORTS = 'supports'
    CONTRADICTS = 'contradicts'
    SUPERSEDES = 'supersedes'
    DEPENDS_ON = 'depends_on'
    DERIVED_FROM = 'derived_from'


@dataclass(frozen=True, slots=True)
class MemoryRelation:
    relation_id: str
    source_memory_id: str
    target_memory_id: str
    kind: MemoryRelationKind
    actor_agent_id: str
    evidence_refs: tuple[str, ...]
    event_anchor_id: str | None
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'relation_id': self.relation_id,
            'source_memory_id': self.source_memory_id,
            'target_memory_id': self.target_memory_id,
            'kind': self.kind.value,
            'actor_agent_id': self.actor_agent_id,
            'evidence_refs': list(self.evidence_refs),
            'event_anchor_id': self.event_anchor_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'MemoryRelation':
        row = cls(
            relation_id=str(state['relation_id']),
            source_memory_id=str(state['source_memory_id']),
            target_memory_id=str(state['target_memory_id']),
            kind=MemoryRelationKind(str(state['kind'])),
            actor_agent_id=str(state['actor_agent_id']),
            evidence_refs=tuple(str(value) for value in state.get('evidence_refs', ())),
            event_anchor_id=None if state.get('event_anchor_id') is None else str(state['event_anchor_id']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('memory relation digest mismatch')
        return row


class MemoryRelationGraph:
    REGION = 'memory-context-knowledge'

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        memory: MemoryFabric,
        events: EventLedger,
        relations: tuple[MemoryRelation, ...] = (),
        counter: int = 0,
    ) -> None:
        self.registry = registry
        self.memory = memory
        self.events = events
        self._relations = list(relations)
        self._counter = int(counter)

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def relations(self) -> tuple[MemoryRelation, ...]:
        return tuple(self._relations)

    def for_memory(self, memory_id: str) -> tuple[MemoryRelation, ...]:
        self.memory.get(memory_id)
        return tuple(
            row for row in self._relations
            if row.source_memory_id == str(memory_id) or row.target_memory_id == str(memory_id)
        )

    def add(
        self,
        *,
        actor_agent_id: str,
        source_memory_id: str,
        target_memory_id: str,
        kind: MemoryRelationKind,
        evidence_refs: tuple[str, ...],
    ) -> MemoryRelation:
        actor = self.registry.get(actor_agent_id)
        if actor.region != self.REGION:
            raise PermissionError('memory semantic relations require a Memory/Context identity')
        self.memory.get(source_memory_id)
        self.memory.get(target_memory_id)
        relation_kind = MemoryRelationKind(kind)
        if not evidence_refs:
            raise ValueError('memory semantic relation requires evidence refs')
        if str(source_memory_id) == str(target_memory_id) and relation_kind in {
            MemoryRelationKind.CONTRADICTS,
            MemoryRelationKind.SUPERSEDES,
        }:
            raise ValueError('memory cannot contradict or supersede itself')
        signature = (str(source_memory_id), str(target_memory_id), relation_kind)
        for existing in self._relations:
            if (existing.source_memory_id, existing.target_memory_id, existing.kind) == signature:
                if existing.evidence_refs != tuple(str(value) for value in evidence_refs):
                    raise ValueError('memory relation cannot be rebound to different evidence')
                return existing
        self._counter += 1
        relation_id = f'memory-relation-{self._counter:08d}'
        anchor = self.events.latest_event_id()
        payload = {
            'relation_id': relation_id,
            'source_memory_id': str(source_memory_id),
            'target_memory_id': str(target_memory_id),
            'kind': relation_kind.value,
            'actor_agent_id': actor.agent_id,
            'evidence_refs': [str(value) for value in evidence_refs],
            'event_anchor_id': anchor,
        }
        row = MemoryRelation(
            relation_id=relation_id,
            source_memory_id=str(source_memory_id),
            target_memory_id=str(target_memory_id),
            kind=relation_kind,
            actor_agent_id=actor.agent_id,
            evidence_refs=tuple(str(value) for value in evidence_refs),
            event_anchor_id=anchor,
            digest=canonical_digest(payload),
        )
        self._relations.append(row)
        return row

    def to_state(self) -> dict[str, Any]:
        return {
            'relations': [row.to_state() for row in self._relations],
            'counter': self._counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        memory: MemoryFabric,
        events: EventLedger,
        state: Mapping[str, Any],
    ) -> 'MemoryRelationGraph':
        relations = tuple(MemoryRelation.from_state(row) for row in state.get('relations', ()))
        result = cls(
            registry=registry,
            memory=memory,
            events=events,
            relations=relations,
            counter=int(state.get('counter', len(relations))),
        )
        seen: set[tuple[str, str, MemoryRelationKind]] = set()
        for row in relations:
            registry.get(row.actor_agent_id)
            memory.get(row.source_memory_id)
            memory.get(row.target_memory_id)
            if row.event_anchor_id is not None:
                events.get(row.event_anchor_id)
            signature = (row.source_memory_id, row.target_memory_id, row.kind)
            if signature in seen:
                raise ValueError('duplicate memory semantic relation in restored state')
            seen.add(signature)
        return result


__all__ = (
    "MemoryLifecycleReceipt",
    "MemoryLifecycleLedger",
    "MemoryRelationKind",
    "MemoryRelation",
    "MemoryRelationGraph",
)
