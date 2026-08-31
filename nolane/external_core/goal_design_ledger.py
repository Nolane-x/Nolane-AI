"""Append-only causal ledger for Goal/Design cognition and authority events.

The ledger deliberately separates speculative cognition, evidence, and closure
authority. Authority transitions are available only through typed methods so a
generic proposal/observation path cannot grant or revoke design authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .goal_design import DecisionReceipt, GoalDesignSnapshot, stable_digest
from .goal_design_authenticity import decision_event_payload, decision_event_subject_refs, verify_decision_receipt


class EventKind(str, Enum):
    OBSERVATION = "observation"
    PROPOSAL = "proposal"
    SNAPSHOT = "snapshot"
    VERIFICATION = "verification"
    DECISION = "decision"
    ASSUMPTION_CHANGE = "assumption_change"
    INVALIDATION = "invalidation"


class AuthorityLevel(str, Enum):
    THOUGHT = "thought"
    EVIDENCE = "evidence"
    AUTHORITY = "authority"


@dataclass(frozen=True)
class GoalDesignEvent:
    event_id: str
    sequence: int
    kind: EventKind
    authority_level: AuthorityLevel
    payload_digest: str
    parent_ids: tuple[str, ...] = ()
    subject_refs: tuple[str, ...] = ()

    def to_state(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "kind": self.kind.value,
            "authority_level": self.authority_level.value,
            "payload_digest": self.payload_digest,
            "parent_ids": list(self.parent_ids),
            "subject_refs": list(self.subject_refs),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "GoalDesignEvent":
        return cls(
            event_id=str(state["event_id"]),
            sequence=int(state["sequence"]),
            kind=EventKind(str(state["kind"])),
            authority_level=AuthorityLevel(str(state["authority_level"])),
            payload_digest=str(state["payload_digest"]),
            parent_ids=tuple(str(x) for x in state.get("parent_ids", ())),
            subject_refs=tuple(str(x) for x in state.get("subject_refs", ())),
        )


class GoalDesignLedger:
    """Content-addressed causal ledger with typed authority transitions."""

    SCHEMA_VERSION = 1

    def __init__(self):
        self._events: list[GoalDesignEvent] = []
        self._by_id: dict[str, GoalDesignEvent] = {}

    @property
    def events(self) -> tuple[GoalDesignEvent, ...]:
        return tuple(self._events)

    @property
    def digest(self) -> str:
        return stable_digest({"goal_design_ledger": self.to_state()})

    def get(self, event_id: str) -> GoalDesignEvent:
        try:
            return self._by_id[str(event_id)]
        except KeyError as exc:
            raise KeyError(f"unknown Goal/Design event: {event_id}") from exc

    def append(
        self,
        kind: EventKind,
        payload: Mapping[str, object],
        *,
        authority_level: AuthorityLevel = AuthorityLevel.THOUGHT,
        parent_ids: tuple[str, ...] = (),
        subject_refs: tuple[str, ...] = (),
    ) -> GoalDesignEvent:
        if authority_level is AuthorityLevel.AUTHORITY:
            raise ValueError("authority events require a typed authority method")
        return self._append(kind, payload, authority_level, parent_ids, subject_refs)

    def record_snapshot(self, snapshot: GoalDesignSnapshot, *, parent_ids: tuple[str, ...] = ()) -> GoalDesignEvent:
        return self._append(
            EventKind.SNAPSHOT,
            {"snapshot_digest": snapshot.digest, "version_vector": snapshot.version_vector.tokens()},
            AuthorityLevel.AUTHORITY,
            parent_ids,
            (snapshot.digest,),
        )

    def record_decision(self, receipt: DecisionReceipt, *, parent_ids: tuple[str, ...] = ()) -> GoalDesignEvent:
        verify_decision_receipt(receipt)
        return self._append(
            EventKind.DECISION,
            decision_event_payload(receipt),
            AuthorityLevel.AUTHORITY,
            parent_ids,
            decision_event_subject_refs(receipt),
        )

    def record_assumption_change(
        self,
        *,
        changed_assumption_ids: tuple[str, ...],
        affected_assumption_ids: tuple[str, ...],
        truth_state_digest: str,
        impact_digest: str,
        parent_ids: tuple[str, ...] = (),
    ) -> GoalDesignEvent:
        """Mint authority that a truth-maintained assumption closure changed."""

        changed = tuple(sorted({str(value).strip() for value in changed_assumption_ids if str(value).strip()}))
        affected = tuple(sorted({str(value).strip() for value in affected_assumption_ids if str(value).strip()}))
        truth_state_digest = str(truth_state_digest).strip()
        impact_digest = str(impact_digest).strip()
        if not changed or not affected or not truth_state_digest or not impact_digest:
            raise ValueError(
                "assumption change authority requires changed/affected assumptions and truth/impact digests"
            )
        if not set(changed).issubset(affected):
            raise ValueError("changed assumptions must be included in affected assumption closure")
        return self._append(
            EventKind.ASSUMPTION_CHANGE,
            {
                "changed_assumption_ids": list(changed),
                "affected_assumption_ids": list(affected),
                "truth_state_digest": truth_state_digest,
                "impact_digest": impact_digest,
            },
            AuthorityLevel.AUTHORITY,
            parent_ids,
            affected,
        )

    def record_invalidation(
        self,
        *,
        receipt_id: str,
        snapshot_digest: str,
        reasons: tuple[str, ...],
        parent_ids: tuple[str, ...] = (),
    ) -> GoalDesignEvent:
        """Mint an authoritative transition that withdraws a prior decision.

        Invalidation is authority, not merely evidence: after this event the
        referenced decision may no longer be treated as active closure.
        """

        receipt_id = str(receipt_id).strip()
        snapshot_digest = str(snapshot_digest).strip()
        normalized_reasons = tuple(sorted({str(reason).strip() for reason in reasons if str(reason).strip()}))
        if not receipt_id or not snapshot_digest or not normalized_reasons:
            raise ValueError("decision invalidation requires receipt, snapshot and at least one reason")
        return self._append(
            EventKind.INVALIDATION,
            {
                "receipt_id": receipt_id,
                "snapshot_digest": snapshot_digest,
                "reasons": list(normalized_reasons),
            },
            AuthorityLevel.AUTHORITY,
            parent_ids,
            (receipt_id,),
        )

    @staticmethod
    def _identity(event: GoalDesignEvent) -> dict[str, Any]:
        return {
            "kind": event.kind.value,
            "authority_level": event.authority_level.value,
            "payload_digest": event.payload_digest,
            "parents": list(event.parent_ids),
            "subjects": list(event.subject_refs),
        }

    def _append(self, kind, payload, authority_level, parent_ids, subject_refs):
        missing = [parent_id for parent_id in parent_ids if parent_id not in self._by_id]
        if missing:
            raise ValueError(f"unknown causal parents: {missing}")
        payload_digest = stable_digest(payload)
        identity = {
            "kind": kind.value,
            "authority_level": authority_level.value,
            "payload_digest": payload_digest,
            "parents": list(parent_ids),
            "subjects": list(subject_refs),
        }
        event_id = stable_digest({"goal_design_event": identity})
        if event_id in self._by_id:
            return self._by_id[event_id]
        event = GoalDesignEvent(
            event_id=event_id,
            sequence=len(self._events) + 1,
            kind=kind,
            authority_level=authority_level,
            payload_digest=payload_digest,
            parent_ids=tuple(parent_ids),
            subject_refs=tuple(subject_refs),
        )
        self._events.append(event)
        self._by_id[event_id] = event
        return event

    def to_state(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "events": [event.to_state() for event in self._events],
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "GoalDesignLedger":
        if int(state.get("schema_version", cls.SCHEMA_VERSION)) != cls.SCHEMA_VERSION:
            raise ValueError("unsupported Goal/Design ledger schema version")
        ledger = cls()
        seen: set[str] = set()
        for expected_sequence, row in enumerate(state.get("events", ()), 1):
            event = GoalDesignEvent.from_state(row)
            if event.sequence != expected_sequence:
                raise ValueError("non-canonical Goal/Design event sequence")
            if event.event_id in seen:
                raise ValueError("duplicate Goal/Design event identity")
            missing = [parent_id for parent_id in event.parent_ids if parent_id not in seen]
            if missing:
                raise ValueError(f"Goal/Design event has unknown or forward causal parents: {missing}")
            expected_id = stable_digest({"goal_design_event": cls._identity(event)})
            if event.event_id != expected_id:
                raise ValueError("Goal/Design event identity digest mismatch")
            ledger._events.append(event)
            ledger._by_id[event.event_id] = event
            seen.add(event.event_id)
        return ledger


__all__ = [
    "AuthorityLevel",
    "EventKind",
    "GoalDesignEvent",
    "GoalDesignLedger",
]
