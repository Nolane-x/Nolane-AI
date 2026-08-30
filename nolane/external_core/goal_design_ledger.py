"""Append-only causal ledger for Goal/Design cognition and authority events."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .goal_design import DecisionReceipt, GoalDesignSnapshot, stable_digest


class EventKind(str, Enum):
    OBSERVATION = "observation"
    PROPOSAL = "proposal"
    SNAPSHOT = "snapshot"
    VERIFICATION = "verification"
    DECISION = "decision"
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


class GoalDesignLedger:
    """Separates speculative cognition from evidence and authority.

    Generic callers cannot self-promote proposals/observations into authority.
    Authority events are minted only through typed snapshot/decision methods.
    """

    def __init__(self):
        self._events: list[GoalDesignEvent] = []
        self._by_id: dict[str, GoalDesignEvent] = {}

    @property
    def events(self) -> tuple[GoalDesignEvent, ...]:
        return tuple(self._events)

    def get(self, event_id: str) -> GoalDesignEvent:
        return self._by_id[event_id]

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
        return self._append(
            EventKind.DECISION,
            {
                "receipt_id": receipt.receipt_id,
                "goal_id": receipt.goal_id,
                "selected_option_id": receipt.selected_option_id,
                "snapshot_digest": receipt.snapshot_digest,
                "evaluation_digest": receipt.evaluation_digest,
            },
            AuthorityLevel.AUTHORITY,
            parent_ids,
            (receipt.goal_id, receipt.selected_option_id, receipt.snapshot_digest),
        )

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
