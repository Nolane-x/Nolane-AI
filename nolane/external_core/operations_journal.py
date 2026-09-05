from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json


@dataclass(frozen=True, slots=True)
class OperationsEvent:
    sequence: int
    transition_id: str
    kind: str
    subject_id: str
    payload_json: str
    previous_digest: str
    digest: str

    @property
    def payload_value(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):
            raise ValueError("operations event payload must decode to an object")
        return value

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "transition_id": self.transition_id,
            "kind": self.kind,
            "subject_id": self.subject_id,
            "payload": self.payload_value,
            "previous_digest": self.previous_digest,
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "transition_id": self.transition_id,
            "kind": self.kind,
            "subject_id": self.subject_id,
            "payload_json": self.payload_json,
            "previous_digest": self.previous_digest,
            "digest": self.digest,
        }

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        transition_id: str,
        kind: str,
        subject_id: str,
        payload: Mapping[str, Any],
        previous_digest: str,
    ) -> "OperationsEvent":
        seq = _positive_int(sequence, "operations journal sequence")
        payload_value = dict(payload)
        _require_finite_json(payload_value)
        payload_json = canonical_json(payload_value)
        semantic = {
            "sequence": seq,
            "transition_id": _explicit(transition_id, "operations transition id"),
            "kind": _explicit(kind, "operations event kind"),
            "subject_id": _explicit(subject_id, "operations event subject id"),
            "payload": payload_value,
            "previous_digest": str(previous_digest),
        }
        return cls(
            sequence=seq,
            transition_id=semantic["transition_id"],
            kind=semantic["kind"],
            subject_id=semantic["subject_id"],
            payload_json=payload_json,
            previous_digest=semantic["previous_digest"],
            digest=canonical_digest(semantic),
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "OperationsEvent":
        payload_json = str(state["payload_json"])
        payload_value = json.loads(payload_json)
        if not isinstance(payload_value, dict):
            raise ValueError("operations journal payload must be an object")
        expected = cls.create(
            sequence=state["sequence"],
            transition_id=str(state["transition_id"]),
            kind=str(state["kind"]),
            subject_id=str(state["subject_id"]),
            payload=payload_value,
            previous_digest=str(state.get("previous_digest", "")),
        )
        if payload_json != expected.payload_json:
            raise ValueError("operations journal payload is not canonical")
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("operations journal event digest mismatch")
        return expected


class OperationsJournal:
    """Append-only canonical operational evidence chain.

    The journal records G-owned operational transitions only. It does not grant
    release, deployment, execution, Assurance, or policy authority.
    """

    def __init__(self) -> None:
        self._events: list[OperationsEvent] = []
        self._by_transition: dict[str, OperationsEvent] = {}

    @property
    def head_digest(self) -> str:
        return self._events[-1].digest if self._events else ""

    @property
    def length(self) -> int:
        return len(self._events)

    @property
    def digest(self) -> str:
        return canonical_digest(self._payload())

    def events(self) -> tuple[OperationsEvent, ...]:
        return tuple(self._events)

    def event_at_sequence(self, sequence: int) -> OperationsEvent:
        seq = _positive_int(sequence, "operations journal sequence")
        try:
            return self._events[seq - 1]
        except IndexError as exc:
            raise KeyError(f"unknown operations journal sequence: {seq}") from exc

    def digest_at_length(self, length: int) -> str:
        count = _non_negative_int(length, "operations journal length")
        if count == 0:
            return ""
        return self.event_at_sequence(count).digest

    def append(
        self,
        *,
        transition_id: str,
        kind: str,
        subject_id: str,
        payload: Mapping[str, Any],
    ) -> OperationsEvent:
        tid = _explicit(transition_id, "operations transition id")
        candidate = OperationsEvent.create(
            sequence=self.length + 1,
            transition_id=tid,
            kind=kind,
            subject_id=subject_id,
            payload=payload,
            previous_digest=self.head_digest,
        )
        existing = self._by_transition.get(tid)
        if existing is not None:
            same_semantics = (
                existing.kind == candidate.kind
                and existing.subject_id == candidate.subject_id
                and existing.payload_json == candidate.payload_json
            )
            if same_semantics:
                return existing
            raise ValueError("operations transition id cannot be rebound")
        self._events.append(candidate)
        self._by_transition[tid] = candidate
        return candidate

    def _payload(self) -> dict[str, Any]:
        return {"events": [row.to_state() for row in self._events]}

    def to_state(self) -> dict[str, Any]:
        payload = self._payload()
        return {**payload, "digest": canonical_digest(payload)}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "OperationsJournal":
        journal = cls()
        for raw in state.get("events", ()):
            parsed = OperationsEvent.from_state(raw)
            if parsed.sequence != journal.length + 1:
                raise ValueError("operations journal sequence discontinuity")
            if parsed.previous_digest != journal.head_digest:
                raise ValueError("operations journal previous digest mismatch")
            replayed = journal.append(
                transition_id=parsed.transition_id,
                kind=parsed.kind,
                subject_id=parsed.subject_id,
                payload=parsed.payload_value,
            )
            if replayed != parsed:
                raise ValueError("operations journal replay mismatch")
        if str(state.get("digest", "")) != journal.digest:
            raise ValueError("operations journal state digest mismatch")
        return journal


def _explicit(value: object, label: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


def _non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer, not bool")
    if value < 0:
        raise ValueError(f"{label} must be non-negative")
    return value


def _positive_int(value: object, label: str) -> int:
    result = _non_negative_int(value, label)
    if result < 1:
        raise ValueError(f"{label} must be positive")
    return result


def _require_finite_json(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain only finite numbers")
        return
    if value is None or isinstance(value, (str, int, bool)):
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings")
            _require_finite_json(child, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _require_finite_json(child, path=f"{path}[{index}]")
        return
    raise ValueError(f"{path} contains a non-canonical JSON value")


__all__ = ("OperationsEvent", "OperationsJournal")
