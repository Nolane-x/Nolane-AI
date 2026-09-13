from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json

COMPONENT_ID = "organization.events"
COMPONENT_VERSION = "0.0.3"
MIGRATED_FROM = "cogcoder.organization.events + cogcoder.organization.types"


_EVENT_STATE_KEYS = (
    "event_id",
    "sequence",
    "kind",
    "source_agent_id",
    "target_agent_id",
    "region",
    "payload_json",
    "digest",
    "scope",
    "causal_parent_ids",
    "object_refs",
    "evidence_refs",
    "priority",
    "requires_ack",
    "status",
    "created_at_logical",
)


def _canonical_state_record(
    state: object,
    expected_keys: tuple[str, ...],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(state, Mapping) or set(state) != set(expected_keys):
        raise ValueError(f"{label} must use canonical serialized state")
    return state


def _canonical_state_list(value: object, label: str) -> list[Any]:
    if type(value) is not list:
        raise ValueError(f"{label} must use canonical serialized state")
    return value


def _exact_string(value: object, label: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{label} must use canonical serialized state")
    return value


def _exact_nullable_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _exact_string(value, label)


def _exact_int(value: object, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must use canonical serialized state")
    return value


def _exact_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{label} must use canonical serialized state")
    return value


def _exact_string_list(value: object, label: str) -> tuple[str, ...]:
    return tuple(
        _exact_string(item, label)
        for item in _canonical_state_list(value, label)
    )


def _canonical_payload_json(value: object) -> str:
    payload_json = _exact_string(value, "event payload_json")
    try:
        payload = json.loads(payload_json)
    except (TypeError, ValueError) as exc:
        raise ValueError("event payload must use canonical JSON object state") from exc
    if not isinstance(payload, dict) or canonical_json(payload) != payload_json:
        raise ValueError("event payload must use canonical JSON object state")
    return payload_json


class EventKind(str, Enum):
    TASK_ASSIGNED = "task_assigned"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_BLOCKED = "task_blocked"
    TASK_COMPLETED = "task_completed"
    PLAN_GAP_DETECTED = "plan_gap_detected"
    PLAN_CHANGE_PROPOSED = "plan_change_proposed"
    PLAN_AMENDED = "plan_amended"
    ARCHITECTURE_CONCERN = "architecture_concern"
    BUG_DISCOVERED = "bug_discovered"
    HYPOTHESIS_PROPOSED = "hypothesis_proposed"
    EVIDENCE_ADDED = "evidence_added"
    TEST_FAILED = "test_failed"
    TEST_PASSED = "test_passed"
    VERIFICATION_REJECTED = "verification_rejected"
    SKILL_CANDIDATE = "skill_candidate"
    SKILL_PROMOTED = "skill_promoted"
    SKILL_REJECTED = "skill_rejected"
    SKILL_QUARANTINED = "skill_quarantined"
    MEMORY_CONFLICT = "memory_conflict"
    MEMORY_PROMOTED = "memory_promoted"
    CENTRAL_INTERVENTION = "central_intervention"
    CENTRAL_QUESTION = "central_question"
    CENTRAL_CORRECTION = "central_correction"
    CENTRAL_REDIRECT = "central_redirect"
    CENTRAL_PAUSE = "central_pause"
    CENTRAL_ABORT = "central_abort"
    CENTRAL_REQUEST_EVIDENCE = "central_request_evidence"
    AGENT_CHECKPOINTED = "agent_checkpointed"
    AGENT_SLEEP = "agent_sleep"
    AGENT_WAKE = "agent_wake"
    CHIEF_DIRECT_WORK = "chief_direct_work"
    NEURAL_CANDIDATE_EVALUATED = "neural_candidate_evaluated"
    NEURAL_PROMOTED = "neural_promoted"
    NEURAL_ROLLBACK = "neural_rollback"
    TASK_LEASE_GRANTED = "task_lease_granted"
    TASK_LEASE_RENEWED = "task_lease_renewed"
    TASK_LEASE_REVOKED = "task_lease_revoked"
    COORDINATION_ACK = "coordination_ack"
    COORDINATION_ESCALATED = "coordination_escalated"
    CONFLICT_OPENED = "conflict_opened"
    CONFLICT_CLAIM_ADDED = "conflict_claim_added"
    CONFLICT_RESOLVED = "conflict_resolved"
    WAKE_RESERVED = "wake_reserved"
    WAKE_DEFERRED = "wake_deferred"
    STALE_AGENT_DETECTED = "stale_agent_detected"


@dataclass(frozen=True, slots=True)
class CognitiveEvent:
    event_id: str
    sequence: int
    kind: EventKind
    source_agent_id: str
    target_agent_id: str | None
    region: str | None
    payload_json: str
    digest: str
    scope: str = "organization"
    causal_parent_ids: tuple[str, ...] = ()
    object_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    priority: int = 0
    requires_ack: bool = False
    status: str = "emitted"
    created_at_logical: int = 0

    @property
    def payload(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):
            raise ValueError("event payload must decode to an object")
        return value

    def to_state(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "kind": self.kind.value,
            "source_agent_id": self.source_agent_id,
            "target_agent_id": self.target_agent_id,
            "region": self.region,
            "payload_json": self.payload_json,
            "digest": self.digest,
            "scope": self.scope,
            "causal_parent_ids": list(self.causal_parent_ids),
            "object_refs": list(self.object_refs),
            "evidence_refs": list(self.evidence_refs),
            "priority": self.priority,
            "requires_ack": self.requires_ack,
            "status": self.status,
            "created_at_logical": self.created_at_logical,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CognitiveEvent":
        state = _canonical_state_record(state, _EVENT_STATE_KEYS, "event")
        return cls(
            event_id=_exact_string(state["event_id"], "event event_id"),
            sequence=_exact_int(state["sequence"], "event sequence"),
            kind=EventKind(_exact_string(state["kind"], "event kind")),
            source_agent_id=_exact_string(state["source_agent_id"], "event source_agent_id"),
            target_agent_id=_exact_nullable_string(state["target_agent_id"], "event target_agent_id"),
            region=_exact_nullable_string(state["region"], "event region"),
            payload_json=_canonical_payload_json(state["payload_json"]),
            digest=_exact_string(state["digest"], "event digest"),
            scope=_exact_string(state["scope"], "event scope"),
            causal_parent_ids=_exact_string_list(state["causal_parent_ids"], "event causal_parent_ids"),
            object_refs=_exact_string_list(state["object_refs"], "event object_refs"),
            evidence_refs=_exact_string_list(state["evidence_refs"], "event evidence_refs"),
            priority=_exact_int(state["priority"], "event priority"),
            requires_ack=_exact_bool(state["requires_ack"], "event requires_ack"),
            status=_exact_string(state["status"], "event status"),
            created_at_logical=_exact_int(state["created_at_logical"], "event created_at_logical"),
        )


@dataclass(frozen=True, slots=True)
class _Subscription:
    kind: EventKind
    region: str | None

    def to_state(self) -> dict[str, str | None]:
        return {"kind": self.kind.value, "region": self.region}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "_Subscription":
        state = _canonical_state_record(state, ("kind", "region"), "event subscription")
        return cls(
            kind=EventKind(_exact_string(state["kind"], "event subscription kind")),
            region=_exact_nullable_string(state["region"], "event subscription region"),
        )


class EventLedger:
    """Canonical append-only causal event ledger."""

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
        scope: str = "organization",
        causal_parent_ids: tuple[str, ...] = (),
        object_refs: tuple[str, ...] = (),
        evidence_refs: tuple[str, ...] = (),
        priority: int = 0,
        requires_ack: bool = False,
        status: str = "emitted",
    ) -> CognitiveEvent:
        sequence = len(self._events) + 1
        event_id = f"evt-{sequence:08d}"
        for parent_id in causal_parent_ids:
            self.get(parent_id)
        payload_json = canonical_json(dict(payload or {}))
        envelope = {
            "event_id": event_id,
            "sequence": sequence,
            "kind": EventKind(kind).value,
            "source_agent_id": str(source_agent_id),
            "target_agent_id": None if target_agent_id is None else str(target_agent_id),
            "region": None if region is None else str(region),
            "payload_json": payload_json,
            "scope": str(scope),
            "causal_parent_ids": list(causal_parent_ids),
            "object_refs": list(object_refs),
            "evidence_refs": list(evidence_refs),
            "priority": int(priority),
            "requires_ack": bool(requires_ack),
            "status": str(status),
            "created_at_logical": sequence,
        }
        digest = canonical_digest(envelope)
        row = CognitiveEvent(
            event_id=event_id,
            sequence=sequence,
            kind=EventKind(kind),
            source_agent_id=str(source_agent_id),
            target_agent_id=None if target_agent_id is None else str(target_agent_id),
            region=None if region is None else str(region),
            payload_json=payload_json,
            digest=digest,
            scope=str(scope),
            causal_parent_ids=tuple(str(value) for value in causal_parent_ids),
            object_refs=tuple(str(value) for value in object_refs),
            evidence_refs=tuple(str(value) for value in evidence_refs),
            priority=int(priority),
            requires_ack=bool(requires_ack),
            status=str(status),
            created_at_logical=sequence,
        )
        self._events.append(row)
        return row

    def get(self, event_id: str) -> CognitiveEvent:
        for row in self._events:
            if row.event_id == str(event_id):
                return row
        raise KeyError(f"unknown event id: {event_id}")

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
            "events": [row.to_state() for row in self._events],
            "subscriptions": {
                agent_id: [row.to_state() for row in rows]
                for agent_id, rows in sorted(self._subscriptions.items())
            },
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EventLedger":
        state = _canonical_state_record(state, ("events", "subscriptions"), "event ledger")
        ledger = cls()
        event_states = _canonical_state_list(state["events"], "event ledger events")
        ledger._events = [CognitiveEvent.from_state(row) for row in event_states]
        expected = 1
        prior_event_ids: set[str] = set()
        for row in ledger._events:
            if row.sequence != expected or row.event_id != f"evt-{expected:08d}":
                raise ValueError("event ledger sequence is not canonical")
            if row.created_at_logical != row.sequence:
                raise ValueError("event created_at_logical must match canonical sequence")
            for parent_id in row.causal_parent_ids:
                if parent_id not in prior_event_ids:
                    raise ValueError("event causal parent must reference a prior event")
            envelope = {
                "event_id": row.event_id,
                "sequence": row.sequence,
                "kind": row.kind.value,
                "source_agent_id": row.source_agent_id,
                "target_agent_id": row.target_agent_id,
                "region": row.region,
                "payload_json": row.payload_json,
                "scope": row.scope,
                "causal_parent_ids": list(row.causal_parent_ids),
                "object_refs": list(row.object_refs),
                "evidence_refs": list(row.evidence_refs),
                "priority": row.priority,
                "requires_ack": row.requires_ack,
                "status": row.status,
                "created_at_logical": row.created_at_logical,
            }
            if row.digest != canonical_digest(envelope):
                raise ValueError("event digest mismatch")
            prior_event_ids.add(row.event_id)
            expected += 1

        subscriptions = state["subscriptions"]
        if not isinstance(subscriptions, Mapping):
            raise ValueError("event ledger subscriptions must use canonical serialized state")
        for agent_id, rows in subscriptions.items():
            agent_id = _exact_string(agent_id, "event subscription agent_id")
            row_states = _canonical_state_list(rows, "event subscription rows")
            bucket: list[_Subscription] = []
            for row_state in row_states:
                row = _Subscription.from_state(row_state)
                if row in bucket:
                    raise ValueError("duplicate subscription row")
                bucket.append(row)
            ledger._subscriptions[agent_id] = bucket
        return ledger


__all__ = (
    "EventKind",
    "CognitiveEvent",
    "EventLedger",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
