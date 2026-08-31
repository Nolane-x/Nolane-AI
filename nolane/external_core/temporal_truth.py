from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest


TRUTH_PROTOCOL = "truth-temporal-context-v1"
INTERVAL_PROTOCOL = "truth-validity-interval-v1"
_TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _strict_timestamp(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a canonical UTC RFC3339 timestamp")
    if value != value.strip() or _TIMESTAMP_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be canonical UTC RFC3339 second precision")
    try:
        parsed = datetime.strptime(value, _TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid UTC timestamp") from exc
    if parsed.strftime(_TIMESTAMP_FORMAT) != value:
        raise ValueError(f"{field} must use canonical UTC RFC3339 representation")
    return value


def _instant(value: str) -> datetime:
    return datetime.strptime(value, _TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)


def _optional_timestamp(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    return _strict_timestamp(value, field)


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} state field(s): {','.join(sorted(extra))}")


@dataclass(frozen=True, slots=True)
class TruthInterval:
    valid_from: str | None
    valid_until: str | None
    digest: str

    @classmethod
    def create(cls, *, valid_from: str | None = None, valid_until: str | None = None) -> "TruthInterval":
        start = _optional_timestamp(valid_from, "valid_from")
        end = _optional_timestamp(valid_until, "valid_until")
        if start is not None and end is not None and _instant(start) >= _instant(end):
            raise ValueError("truth validity interval must have valid_from < valid_until")
        payload = {
            "protocol": INTERVAL_PROTOCOL,
            "valid_from": start,
            "valid_until": end,
        }
        return cls(start, end, canonical_digest(payload))

    def state_at(self, as_of: str) -> str:
        current = _instant(_strict_timestamp(as_of, "as_of"))
        if self.valid_from is not None and current < _instant(self.valid_from):
            return "not_yet_valid"
        if self.valid_until is not None and current >= _instant(self.valid_until):
            return "expired"
        return "active"

    def contains(self, as_of: str) -> bool:
        return self.state_at(as_of) == "active"

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": INTERVAL_PROTOCOL,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TruthInterval":
        _unexpected(state, {"protocol", "valid_from", "valid_until", "digest"}, "truth interval")
        if str(state.get("protocol", "")) != INTERVAL_PROTOCOL:
            raise ValueError("unsupported truth interval protocol")
        row = cls.create(
            valid_from=None if state.get("valid_from") is None else str(state["valid_from"]),
            valid_until=None if state.get("valid_until") is None else str(state["valid_until"]),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("truth interval digest mismatch")
        return row


@dataclass(frozen=True, slots=True)
class TemporalContext:
    as_of: str
    digest: str

    @classmethod
    def create(cls, *, as_of: str) -> "TemporalContext":
        canonical = _strict_timestamp(as_of, "as_of")
        payload = {"protocol": TRUTH_PROTOCOL, "as_of": canonical}
        return cls(canonical, canonical_digest(payload))

    def to_state(self) -> dict[str, str]:
        return {"protocol": TRUTH_PROTOCOL, "as_of": self.as_of, "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TemporalContext":
        _unexpected(state, {"protocol", "as_of", "digest"}, "temporal context")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported temporal context protocol")
        row = cls.create(as_of=str(state["as_of"]))
        if str(state["digest"]) != row.digest:
            raise ValueError("temporal context digest mismatch")
        return row


__all__ = (
    "TRUTH_PROTOCOL",
    "INTERVAL_PROTOCOL",
    "TruthInterval",
    "TemporalContext",
)
