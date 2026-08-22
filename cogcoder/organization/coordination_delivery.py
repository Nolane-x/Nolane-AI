from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .events import EventLedger
from .registry import AgentRegistry
from .types import EventKind, canonical_digest


class AckStatus(str, Enum):
    NOT_REQUIRED = 'not_required'
    PENDING = 'pending'
    ACKED = 'acked'
    ESCALATED = 'escalated'


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    delivery_id: str
    event_id: str
    recipient_agent_id: str
    event_sequence: int
    delivered_at_logical: int
    requires_ack: bool
    ack_status: AckStatus
    ack_event_id: str | None
    source_event_digest: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'delivery_id': self.delivery_id,
            'event_id': self.event_id,
            'recipient_agent_id': self.recipient_agent_id,
            'event_sequence': self.event_sequence,
            'delivered_at_logical': self.delivered_at_logical,
            'requires_ack': self.requires_ack,
            'ack_status': self.ack_status.value,
            'ack_event_id': self.ack_event_id,
            'source_event_digest': self.source_event_digest,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'DeliveryReceipt':
        row = cls(
            delivery_id=str(state['delivery_id']), event_id=str(state['event_id']),
            recipient_agent_id=str(state['recipient_agent_id']),
            event_sequence=int(state['event_sequence']),
            delivered_at_logical=int(state['delivered_at_logical']),
            requires_ack=bool(state['requires_ack']),
            ack_status=AckStatus(str(state['ack_status'])),
            ack_event_id=None if state.get('ack_event_id') is None else str(state['ack_event_id']),
            source_event_digest=str(state['source_event_digest']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('delivery receipt digest mismatch')
        return row


class DeliveryCoordinator:
    def __init__(
        self, *, registry: AgentRegistry, events: EventLedger,
        receipts: tuple[DeliveryReceipt, ...] = (), counter: int = 0,
    ) -> None:
        self.registry = registry
        self.events = events
        self._receipts: dict[str, DeliveryReceipt] = {}
        self._by_key: dict[tuple[str, str], str] = {}
        for row in receipts:
            self._validate_row(row)
            key = (row.event_id, row.recipient_agent_id)
            if key in self._by_key:
                raise ValueError('duplicate delivery receipt key')
            self._receipts[row.delivery_id] = row
            self._by_key[key] = row.delivery_id
        self._counter = int(counter)
        if self._counter < len(self._receipts):
            raise ValueError('delivery counter is not canonical')

    def _validate_row(self, row: DeliveryReceipt) -> None:
        self.registry.get(row.recipient_agent_id)
        event = self.events.get(row.event_id)
        if event.sequence != row.event_sequence or event.digest != row.source_event_digest:
            raise ValueError('delivery receipt disagrees with source event')
        expected_status = AckStatus.PENDING if event.requires_ack else AckStatus.NOT_REQUIRED
        if row.ack_status in (AckStatus.PENDING, AckStatus.NOT_REQUIRED) and row.ack_status is not expected_status:
            raise ValueError('delivery ACK disposition disagrees with source event')
        if row.ack_status is AckStatus.ACKED:
            if row.ack_event_id is None:
                raise ValueError('ACKED delivery requires ack event')
            ack = self.events.get(row.ack_event_id)
            if ack.kind is not EventKind.COORDINATION_ACK:
                raise ValueError('delivery ACK references wrong event kind')
            if ack.source_agent_id != row.recipient_agent_id or row.event_id not in ack.causal_parent_ids:
                raise ValueError('delivery ACK recipient or source event mismatch')
        elif row.ack_event_id is not None:
            raise ValueError('non-ACKED delivery cannot carry ack event')

    def deliver(self, event_id: str, recipient_agent_id: str) -> DeliveryReceipt:
        event = self.events.get(event_id)
        recipient = self.registry.get(recipient_agent_id)
        key = (event.event_id, recipient.agent_id)
        existing_id = self._by_key.get(key)
        if existing_id is not None:
            return self._receipts[existing_id]
        for parent_id in event.causal_parent_ids:
            if (parent_id, recipient.agent_id) not in self._by_key:
                raise ValueError(
                    f'causal parent {parent_id} must be delivered to {recipient.agent_id} before child {event.event_id}'
                )
        self._counter += 1
        temp = DeliveryReceipt(
            delivery_id=f'delivery-{self._counter:08d}',
            event_id=event.event_id, recipient_agent_id=recipient.agent_id,
            event_sequence=event.sequence, delivered_at_logical=event.created_at_logical,
            requires_ack=event.requires_ack,
            ack_status=AckStatus.PENDING if event.requires_ack else AckStatus.NOT_REQUIRED,
            ack_event_id=None, source_event_digest=event.digest, digest='',
        )
        row = replace(temp, digest=canonical_digest(temp.payload()))
        self._receipts[row.delivery_id] = row
        self._by_key[key] = row.delivery_id
        return row

    def acknowledge(self, delivery_id: str, agent_id: str) -> DeliveryReceipt:
        row = self.get(delivery_id)
        actor = self.registry.get(agent_id)
        if actor.agent_id != row.recipient_agent_id:
            raise PermissionError('only the delivery recipient may acknowledge it')
        if not row.requires_ack:
            raise ValueError('delivery does not require acknowledgement')
        if row.ack_status is AckStatus.ACKED:
            return row
        if row.ack_status is AckStatus.ESCALATED:
            raise PermissionError('escalated delivery requires explicit reconciliation')
        event = self.events.get(row.event_id)
        if event.digest != row.source_event_digest:
            raise ValueError('source event changed after delivery')
        ack = self.events.append(
            EventKind.COORDINATION_ACK,
            source_agent_id=actor.agent_id,
            target_agent_id=event.source_agent_id,
            region=actor.region,
            causal_parent_ids=(event.event_id,),
            object_refs=event.object_refs,
            payload={'delivery_id': row.delivery_id, 'event_id': row.event_id},
        )
        temp = replace(row, ack_status=AckStatus.ACKED, ack_event_id=ack.event_id, digest='')
        updated = replace(temp, digest=canonical_digest(temp.payload()))
        self._receipts[row.delivery_id] = updated
        return updated

    def escalate(self, delivery_id: str) -> DeliveryReceipt:
        row = self.get(delivery_id)
        if row.ack_status is AckStatus.ACKED:
            return row
        temp = replace(row, ack_status=AckStatus.ESCALATED, ack_event_id=None, digest='')
        updated = replace(temp, digest=canonical_digest(temp.payload()))
        self._receipts[row.delivery_id] = updated
        return updated

    def get(self, delivery_id: str) -> DeliveryReceipt:
        try:
            return self._receipts[str(delivery_id)]
        except KeyError as exc:
            raise KeyError(f'unknown delivery id: {delivery_id}') from exc

    def for_event(self, event_id: str) -> tuple[DeliveryReceipt, ...]:
        return tuple(row for row in self.receipts() if row.event_id == str(event_id))

    def for_event_recipient(self, event_id: str, recipient_agent_id: str) -> DeliveryReceipt:
        key = (str(event_id), str(recipient_agent_id))
        try:
            return self._receipts[self._by_key[key]]
        except KeyError as exc:
            raise KeyError(f'event {event_id} not delivered to {recipient_agent_id}') from exc

    def receipts(self) -> tuple[DeliveryReceipt, ...]:
        return tuple(self._receipts[key] for key in sorted(self._receipts))

    def to_state(self) -> dict[str, Any]:
        return {
            'receipts': [row.to_state() for row in self.receipts()],
            'counter': self._counter,
        }

    @classmethod
    def from_state(
        cls, *, registry: AgentRegistry, events: EventLedger, state: Mapping[str, Any],
    ) -> 'DeliveryCoordinator':
        receipts = tuple(DeliveryReceipt.from_state(x) for x in state.get('receipts', ()))
        return cls(
            registry=registry, events=events, receipts=receipts,
            counter=int(state.get('counter', len(receipts))),
        )
