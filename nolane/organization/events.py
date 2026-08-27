from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json

COMPONENT_ID = "organization.events"
COMPONENT_VERSION = "0.0.2"
MIGRATED_FROM = "cogcoder.organization.events + cogcoder.organization.types"


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
        return cls(
            event_id=str(state["event_id"]),
            sequence=int(state["sequence"]),
            kind=EventKind(str(state["kind"])),
            source_agent_id=str(state["source_agent_id"]),
            target_agent_id=None if state.get("target_agent_id") is None else str(state["target_agent_id"]),
            region=None if state.get("region") is None else str(state["region"]),
            payload_json=str(state["payload_json"]),
            digest=str(state["digest"]),
            scope=str(state.get("scope", "organization")),
            causal_parent_ids=tuple(str(row) for row in state.get("causal_parent_ids", ())),
            object_refs=tuple(str(row) for row in state.get("object_refs", ())),
            evidence_refs=tuple(str(row) for row in state.get("evidence_refs", ())),
            priority=int(state.get("priority", 0)),
            requires_ack=bool(state.get("requires_ack", False)),
            status=str(state.get("status", "emitted")),
            created_at_logical=int(state.get("created_at_logical", state.get("sequence", 0))),
        )


@dataclass(frozen=True, slots=True)
class _Subscription:
    kind: EventKind
    region: str | None

    def to_state(self) -> dict[str, str | None]:
        return {"kind": self.kind.value, "region": self.region}


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
        ledger = cls()
        ledger._events = [CognitiveEvent.from_state(row) for row in state.get("events", ())]
        expected = 1
        for row in ledger._events:
            if row.sequence != expected or row.event_id != f"evt-{expected:08d}":
                raise ValueError("event ledger sequence is not canonical")
            expected += 1
        for agent_id, rows in state.get("subscriptions", {}).items():
            ledger._subscriptions[str(agent_id)] = [
                _Subscription(EventKind(str(row["kind"])), None if row.get("region") is None else str(row["region"]))
                for row in rows
            ]
        return ledger


__all__ = (
    "EventKind",
    "CognitiveEvent",
    "EventLedger",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
