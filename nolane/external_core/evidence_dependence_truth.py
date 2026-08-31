from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest


PARENT_COMPONENT_ID = "external.evidence"
TRUTH_PROTOCOL = "truth-source-dependence-v8"
PROJECTION_PROTOCOL = "truth-source-dependence-projection-v8"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _ids(values: tuple[str, ...], field: str, *, require_nonempty: bool = True) -> tuple[str, ...]:
    rows = tuple(sorted(str(value).strip() for value in values))
    if any(not value for value in rows) or len(set(rows)) != len(rows):
        raise ValueError(f"{field} must be explicit and unique")
    if require_nonempty and not rows:
        raise ValueError(f"{field} must be non-empty")
    return rows


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


@dataclass(frozen=True, slots=True)
class SourceDependenceRevision:
    source_id: str
    revision: int
    predecessor_digest: str
    basis_ids: tuple[str, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        revision: int,
        predecessor_digest: str = "",
        basis_ids: tuple[str, ...],
    ) -> "SourceDependenceRevision":
        source_id = _explicit(source_id, "source dependence source_id")
        revision = int(revision)
        if revision < 1:
            raise ValueError("source dependence revision must be positive")
        predecessor_digest = str(predecessor_digest).strip()
        if revision == 1 and predecessor_digest:
            raise ValueError("first source dependence revision cannot have predecessor")
        if revision > 1 and not predecessor_digest:
            raise ValueError("later source dependence revision requires predecessor digest")
        bases = _ids(tuple(basis_ids), "source dependence basis ids")
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "source_id": source_id,
            "revision": revision,
            "predecessor_digest": predecessor_digest,
            "basis_ids": list(bases),
        }
        return cls(
            source_id,
            revision,
            predecessor_digest,
            bases,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "source_id": self.source_id,
            "revision": self.revision,
            "predecessor_digest": self.predecessor_digest,
            "basis_ids": list(self.basis_ids),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "SourceDependenceRevision":
        _unexpected(
            state,
            {
                "protocol",
                "source_id",
                "revision",
                "predecessor_digest",
                "basis_ids",
                "digest",
            },
            "source dependence revision",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported source dependence revision protocol")
        row = cls.create(
            source_id=str(state["source_id"]),
            revision=int(state["revision"]),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            basis_ids=tuple(str(value) for value in state.get("basis_ids", ())),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("source dependence revision digest mismatch")
        return row


class SourceDependenceRegistry:
    """Append-only common-basis dependence sidecar under ``external.evidence``."""

    def __init__(self) -> None:
        self._revisions: dict[str, list[SourceDependenceRevision]] = {}

    def revisions(self, source_id: str) -> tuple[SourceDependenceRevision, ...]:
        return tuple(self._revisions.get(str(source_id), ()))

    def current(self, source_id: str) -> SourceDependenceRevision | None:
        rows = self.revisions(source_id)
        return rows[-1] if rows else None

    def basis_ids(self, source_id: str) -> tuple[str, ...]:
        row = self.current(str(source_id))
        if row is None:
            raise KeyError(f"unknown source dependence identity: {source_id}")
        return row.basis_ids

    def register(self, row: SourceDependenceRevision) -> SourceDependenceRevision:
        if not isinstance(row, SourceDependenceRevision):
            raise TypeError("source dependence registry accepts canonical revisions only")

        history = self._revisions.get(row.source_id, [])
        if not history:
            if row.revision != 1:
                raise ValueError("source dependence revision sequence must start at 1")
            if row.predecessor_digest:
                raise ValueError("first source dependence revision cannot have predecessor")
        else:
            current = history[-1]
            if row.revision == current.revision:
                if row != current:
                    raise ValueError("source dependence revision collision")
                return current
            if row.revision != current.revision + 1:
                raise ValueError("source dependence revision sequence must advance exactly once")
            if row.predecessor_digest != current.digest:
                raise ValueError("source dependence predecessor mismatch")

        self._revisions.setdefault(row.source_id, []).append(row)
        return row

    def projection_state(self, source_ids: tuple[str, ...]) -> dict[str, Any]:
        requested = _ids(
            tuple(source_ids),
            "source dependence projection ids",
            require_nonempty=False,
        )
        rows: list[dict[str, Any]] = []
        for source_id in requested:
            row = self.current(source_id)
            if row is None:
                rows.append({"source_id": source_id, "status": "missing"})
            else:
                rows.append(
                    {
                        "source_id": source_id,
                        "status": "registered",
                        "revision": row.to_state(),
                    }
                )
        return {
            "protocol": PROJECTION_PROTOCOL,
            "requested_source_ids": list(requested),
            "sources": rows,
        }

    def projection_digest(self, source_ids: tuple[str, ...]) -> str:
        return canonical_digest(self.projection_state(tuple(source_ids)))

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "revisions": [
                row.to_state()
                for source_id in sorted(self._revisions)
                for row in self._revisions[source_id]
            ],
        }

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "SourceDependenceRegistry":
        _unexpected(state, {"protocol", "revisions"}, "source dependence registry")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported source dependence protocol")

        parsed: list[SourceDependenceRevision] = []
        seen: set[tuple[str, int]] = set()
        for value in state.get("revisions", ()):
            row = SourceDependenceRevision.from_state(value)
            key = (row.source_id, row.revision)
            if key in seen:
                raise ValueError("duplicate serialized source dependence revision")
            seen.add(key)
            parsed.append(row)

        registry = cls()
        for row in sorted(parsed, key=lambda item: (item.source_id, item.revision)):
            registry.register(row)
        return registry


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "PROJECTION_PROTOCOL",
    "SourceDependenceRevision",
    "SourceDependenceRegistry",
)
