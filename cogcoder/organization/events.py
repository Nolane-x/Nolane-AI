from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .types import CognitiveEvent, EventKind, canonical_digest, canonical_json


@dataclass(frozen=True, slots=True)
class _Subscription:
    kind: EventKind
    region: str | None

    def to_state(self) -> dict[str, str | None]:
        return {'kind': self.kind.value, 'region': self.region}


class EventLedger:
    def __init__(self) -> None:
        self._events: list[CognitiveEvent] = []
        self._subscriptions: dict[str, list[_Subscription]] = {}

    def subscribe(self, agent_id: str, kind: EventKind, *, region: str | None = None) -> None:
        row = _Subscription(EventKind(kind), None if region is None else str(region))
        bucket = self._subscriptions.setdefault(str(agent_id), [])
        if row not in bucket:
            bucket.append(row)

    def append(
        self,
        kind: EventKind,
        *,
        source_agent_id: str,
        target_agent_id: str | None = None,
        region: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> CognitiveEvent:
        sequence = len(self._events) + 1
        event_id = f'evt-{sequence:08d}'
        payload_json = canonical_json(dict(payload or {}))
        digest = canonical_digest(
            {
                'event_id': event_id,
                'sequence': sequence,
                'kind': EventKind(kind).value,
                'source_agent_id': str(source_agent_id),
                'target_agent_id': None if target_agent_id is None else str(target_agent_id),
                'region': None if region is None else str(region),
                'payload_json': payload_json,
            }
        )
        row = CognitiveEvent(
            event_id=event_id,
            sequence=sequence,
            kind=EventKind(kind),
            source_agent_id=str(source_agent_id),
            target_agent_id=None if target_agent_id is None else str(target_agent_id),
            region=None if region is None else str(region),
            payload_json=payload_json,
            digest=digest,
        )
        self._events.append(row)
        return row

    def get(self, event_id: str) -> CognitiveEvent:
        for row in self._events:
            if row.event_id == str(event_id):
                return row
        raise KeyError(f'unknown event id: {event_id}')

    def events_since(self, event_id: str | None) -> tuple[CognitiveEvent, ...]:
        if event_id is None:
            return tuple(self._events)
        anchor = self.get(event_id)
        return tuple(row for row in self._events if row.sequence > anchor.sequence)

    def deliverable_for(self, agent_id: str) -> tuple[CognitiveEvent, ...]:
        target = str(agent_id)
        subscriptions = tuple(self._subscriptions.get(target, ()))
        rows: list[CognitiveEvent] = []
        for event in self._events:
            direct = event.target_agent_id == target
            subscribed = any(
                sub.kind is event.kind and (sub.region is None or sub.region == event.region)
                for sub in subscriptions
            )
            if direct or subscribed:
                rows.append(event)
        return tuple(rows)

    def latest_event_id(self) -> str | None:
        return None if not self._events else self._events[-1].event_id

    def to_state(self) -> dict[str, Any]:
        return {
            'events': [row.to_state() for row in self._events],
            'subscriptions': {
                agent_id: [row.to_state() for row in rows]
                for agent_id, rows in sorted(self._subscriptions.items())
            },
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'EventLedger':
        ledger = cls()
        ledger._events = [CognitiveEvent.from_state(row) for row in state.get('events', ())]
        expected = 1
        for row in ledger._events:
            if row.sequence != expected or row.event_id != f'evt-{expected:08d}':
                raise ValueError('event ledger sequence is not canonical')
            expected += 1
        for agent_id, rows in state.get('subscriptions', {}).items():
            ledger._subscriptions[str(agent_id)] = [
                _Subscription(EventKind(str(row['kind'])), None if row.get('region') is None else str(row['region']))
                for row in rows
            ]
        return ledger
