from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest


PARENT_COMPONENT_ID = "external.evidence"
TRUTH_PROTOCOL = "truth-source-provenance-v5"
PROJECTION_PROTOCOL = "truth-source-provenance-projection-v5"


def _explicit(value: str, field: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field} must be explicit")
    return value


def _ids(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    rows = tuple(sorted(str(value).strip() for value in values))
    if any(not value for value in rows) or len(set(rows)) != len(rows):
        raise ValueError(f"{field} must be explicit and unique")
    return rows


def _unexpected(state: Mapping[str, Any], allowed: set[str], kind: str) -> None:
    extra = set(state) - allowed
    if extra:
        raise ValueError(f"unexpected {kind} field(s): {','.join(sorted(extra))}")


@dataclass(frozen=True, slots=True)
class SourceProvenanceRevision:
    source_id: str
    revision: int
    predecessor_digest: str
    controller_id: str
    parent_source_ids: tuple[str, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        source_id: str,
        revision: int,
        predecessor_digest: str = "",
        controller_id: str,
        parent_source_ids: tuple[str, ...] = (),
    ) -> "SourceProvenanceRevision":
        source_id = _explicit(source_id, "source provenance source_id")
        controller_id = _explicit(controller_id, "source provenance controller_id")
        revision = int(revision)
        if revision < 1:
            raise ValueError("source provenance revision must be positive")
        predecessor_digest = str(predecessor_digest).strip()
        if revision == 1 and predecessor_digest:
            raise ValueError("first source provenance revision cannot have predecessor")
        if revision > 1 and not predecessor_digest:
            raise ValueError("later source provenance revision requires predecessor digest")
        parents = _ids(tuple(parent_source_ids), "source provenance parent ids")
        if source_id in parents:
            raise ValueError("source provenance cannot directly parent itself")
        payload = {
            "protocol": TRUTH_PROTOCOL,
            "source_id": source_id,
            "revision": revision,
            "predecessor_digest": predecessor_digest,
            "controller_id": controller_id,
            "parent_source_ids": list(parents),
        }
        return cls(
            source_id,
            revision,
            predecessor_digest,
            controller_id,
            parents,
            canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": TRUTH_PROTOCOL,
            "source_id": self.source_id,
            "revision": self.revision,
            "predecessor_digest": self.predecessor_digest,
            "controller_id": self.controller_id,
            "parent_source_ids": list(self.parent_source_ids),
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "SourceProvenanceRevision":
        _unexpected(
            state,
            {
                "protocol",
                "source_id",
                "revision",
                "predecessor_digest",
                "controller_id",
                "parent_source_ids",
                "digest",
            },
            "source provenance revision",
        )
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported source provenance revision protocol")
        row = cls.create(
            source_id=str(state["source_id"]),
            revision=int(state["revision"]),
            predecessor_digest=str(state.get("predecessor_digest", "")),
            controller_id=str(state["controller_id"]),
            parent_source_ids=tuple(str(value) for value in state.get("parent_source_ids", ())),
        )
        if str(state["digest"]) != row.digest:
            raise ValueError("source provenance revision digest mismatch")
        return row


class SourceProvenanceRegistry:
    """Append-only source-lineage authority sidecar under ``external.evidence``.

    Independence is derived from live controller ancestry. A record can describe
    mirrors and aggregates, but only a lineage with exactly one controller root
    contributes an independent verification identity.
    """

    def __init__(self) -> None:
        self._revisions: dict[str, list[SourceProvenanceRevision]] = {}

    def revisions(self, source_id: str) -> tuple[SourceProvenanceRevision, ...]:
        return tuple(self._revisions.get(str(source_id), ()))

    def current(self, source_id: str) -> SourceProvenanceRevision | None:
        rows = self.revisions(source_id)
        return rows[-1] if rows else None

    @staticmethod
    def _assert_acyclic(current: Mapping[str, SourceProvenanceRevision]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(source_id: str) -> None:
            if source_id in visited:
                return
            if source_id in visiting:
                raise ValueError("source provenance graph contains a cycle")
            visiting.add(source_id)
            row = current[source_id]
            for parent_id in row.parent_source_ids:
                if parent_id not in current:
                    raise ValueError(f"unknown source provenance parent: {parent_id}")
                visit(parent_id)
            visiting.remove(source_id)
            visited.add(source_id)

        for source_id in sorted(current):
            visit(source_id)

    def register(self, row: SourceProvenanceRevision) -> SourceProvenanceRevision:
        if not isinstance(row, SourceProvenanceRevision):
            raise TypeError("source provenance registry accepts canonical revisions only")

        history = self._revisions.get(row.source_id, [])
        if not history:
            if row.revision != 1:
                raise ValueError("source provenance revision sequence must start at 1")
            if row.predecessor_digest:
                raise ValueError("first source provenance revision cannot have predecessor")
        else:
            current = history[-1]
            if row.revision == current.revision:
                if row != current:
                    raise ValueError("source provenance revision collision")
                return current
            if row.revision != current.revision + 1:
                raise ValueError("source provenance revision sequence must advance exactly once")
            if row.predecessor_digest != current.digest:
                raise ValueError("source provenance predecessor mismatch")

        current_map = {
            source_id: values[-1]
            for source_id, values in self._revisions.items()
            if values
        }
        for parent_id in row.parent_source_ids:
            if parent_id not in current_map:
                raise ValueError(f"unknown source provenance parent: {parent_id}")
        current_map[row.source_id] = row
        self._assert_acyclic(current_map)

        self._revisions.setdefault(row.source_id, []).append(row)
        return row

    def root_controllers(self, source_id: str) -> tuple[str, ...]:
        source_id = str(source_id)
        if self.current(source_id) is None:
            raise KeyError(f"unknown source provenance identity: {source_id}")

        memo: dict[str, set[str]] = {}

        def roots(current_id: str) -> set[str]:
            if current_id in memo:
                return set(memo[current_id])
            row = self.current(current_id)
            if row is None:
                raise KeyError(f"unknown source provenance identity: {current_id}")
            result = {row.controller_id}
            for parent_id in row.parent_source_ids:
                result.update(roots(parent_id))
            memo[current_id] = set(result)
            return result

        return tuple(sorted(roots(source_id)))

    def independence_key(self, source_id: str) -> str | None:
        try:
            roots = self.root_controllers(str(source_id))
        except KeyError:
            return None
        return roots[0] if len(roots) == 1 else None

    def projection_state(self, source_ids: tuple[str, ...]) -> dict[str, Any]:
        requested = _ids(tuple(source_ids), "source provenance projection ids")
        included: set[str] = set()
        missing: set[str] = set()

        def collect(source_id: str) -> None:
            if source_id in included or source_id in missing:
                return
            row = self.current(source_id)
            if row is None:
                missing.add(source_id)
                return
            included.add(source_id)
            for parent_id in row.parent_source_ids:
                collect(parent_id)

        for source_id in requested:
            collect(source_id)

        rows: list[dict[str, Any]] = []
        for source_id in sorted(set(requested) | included | missing):
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
    def from_state(cls, state: Mapping[str, Any]) -> "SourceProvenanceRegistry":
        _unexpected(state, {"protocol", "revisions"}, "source provenance registry")
        if str(state.get("protocol", "")) != TRUTH_PROTOCOL:
            raise ValueError("unsupported source provenance protocol")

        parsed: list[SourceProvenanceRevision] = []
        seen: set[tuple[str, int]] = set()
        for value in state.get("revisions", ()):
            row = SourceProvenanceRevision.from_state(value)
            key = (row.source_id, row.revision)
            if key in seen:
                raise ValueError("duplicate serialized source provenance revision")
            seen.add(key)
            parsed.append(row)

        registry = cls()
        pending = sorted(parsed, key=lambda item: (item.revision, item.source_id))
        while pending:
            progressed = False
            remainder: list[SourceProvenanceRevision] = []
            for row in pending:
                history = registry.revisions(row.source_id)
                sequence_ready = (
                    (row.revision == 1 and not history)
                    or (history and row.revision == history[-1].revision + 1)
                )
                parents_ready = all(registry.current(parent) is not None for parent in row.parent_source_ids)
                if sequence_ready and parents_ready:
                    registry.register(row)
                    progressed = True
                else:
                    remainder.append(row)
            if not progressed:
                raise ValueError("source provenance restore ordering or cycle failure")
            pending = remainder
        return registry


__all__ = (
    "PARENT_COMPONENT_ID",
    "TRUTH_PROTOCOL",
    "PROJECTION_PROTOCOL",
    "SourceProvenanceRevision",
    "SourceProvenanceRegistry",
)
