from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping


COMPONENT_ID = "external.memory.fabric"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.memory + cogcoder.organization.types"


class MemoryScope(str, Enum):
    GLOBAL = "global"
    REGION = "region"
    PERSONAL = "personal"
    TASK = "task"
    PRIVATE = "private"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    STALE = "stale"
    SUPERSEDED = "superseded"
    CONTRADICTED = "contradicted"
    QUARANTINED = "quarantined"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    memory_id: str
    sequence: int
    scope: MemoryScope
    text: str
    owner_agent_id: str
    region: str | None = None
    task_id: str | None = None
    tags: tuple[str, ...] = ()
    parent_memory_id: str | None = None
    promotion_receipt_id: str | None = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 1.0
    dependencies: tuple[str, ...] = ()
    supersedes: str | None = None
    status_reason: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("memory confidence must lie in [0, 1]")

    def to_state(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "sequence": self.sequence,
            "scope": self.scope.value,
            "text": self.text,
            "owner_agent_id": self.owner_agent_id,
            "region": self.region,
            "task_id": self.task_id,
            "tags": list(self.tags),
            "parent_memory_id": self.parent_memory_id,
            "promotion_receipt_id": self.promotion_receipt_id,
            "status": self.status.value,
            "evidence_ids": list(self.evidence_ids),
            "confidence": self.confidence,
            "dependencies": list(self.dependencies),
            "supersedes": self.supersedes,
            "status_reason": self.status_reason,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "MemoryEntry":
        return cls(
            memory_id=str(state["memory_id"]),
            sequence=int(state["sequence"]),
            scope=MemoryScope(str(state["scope"])),
            text=str(state["text"]),
            owner_agent_id=str(state["owner_agent_id"]),
            region=None if state.get("region") is None else str(state["region"]),
            task_id=None if state.get("task_id") is None else str(state["task_id"]),
            tags=tuple(str(row) for row in state.get("tags", ())),
            parent_memory_id=None if state.get("parent_memory_id") is None else str(state["parent_memory_id"]),
            promotion_receipt_id=None if state.get("promotion_receipt_id") is None else str(state["promotion_receipt_id"]),
            status=MemoryStatus(str(state.get("status", MemoryStatus.ACTIVE.value))),
            evidence_ids=tuple(str(row) for row in state.get("evidence_ids", ())),
            confidence=float(state.get("confidence", 1.0)),
            dependencies=tuple(str(row) for row in state.get("dependencies", ())),
            supersedes=None if state.get("supersedes") is None else str(state["supersedes"]),
            status_reason=None if state.get("status_reason") is None else str(state["status_reason"]),
        )


class MemoryFabric:
    def __init__(self) -> None:
        self._entries: list[MemoryEntry] = []

    def write(
        self,
        scope: MemoryScope,
        text: str,
        *,
        owner_agent_id: str,
        region: str | None = None,
        task_id: str | None = None,
        tags: tuple[str, ...] = (),
        parent_memory_id: str | None = None,
        promotion_receipt_id: str | None = None,
        evidence_ids: tuple[str, ...] = (),
        confidence: float = 1.0,
        dependencies: tuple[str, ...] = (),
        supersedes: str | None = None,
        initial_status: MemoryStatus = MemoryStatus.ACTIVE,
        status_reason: str | None = None,
    ) -> MemoryEntry:
        scope = MemoryScope(scope)
        initial_status = MemoryStatus(initial_status)
        if not str(text).strip():
            raise ValueError("memory text must be non-empty")
        if not str(owner_agent_id).strip():
            raise ValueError("memory owner must be explicit")
        if scope is MemoryScope.REGION and not region:
            raise ValueError("regional memory requires a region")
        if scope is MemoryScope.TASK and not task_id:
            raise ValueError("task memory requires a task id")
        if initial_status is not MemoryStatus.ACTIVE and not str(status_reason or "").strip():
            raise ValueError("inactive memory state requires a reason")
        if supersedes is not None:
            self.get(supersedes)
        sequence = len(self._entries) + 1
        row = MemoryEntry(
            memory_id=f"mem-{sequence:08d}",
            sequence=sequence,
            scope=scope,
            text=str(text),
            owner_agent_id=str(owner_agent_id),
            region=None if region is None else str(region),
            task_id=None if task_id is None else str(task_id),
            tags=tuple(sorted({str(tag) for tag in tags})),
            parent_memory_id=None if parent_memory_id is None else str(parent_memory_id),
            promotion_receipt_id=None if promotion_receipt_id is None else str(promotion_receipt_id),
            status=initial_status,
            evidence_ids=tuple(sorted({str(value) for value in evidence_ids})),
            confidence=float(confidence),
            dependencies=tuple(sorted({str(value) for value in dependencies})),
            supersedes=None if supersedes is None else str(supersedes),
            status_reason=None if initial_status is MemoryStatus.ACTIVE else str(status_reason),
        )
        self._entries.append(row)
        if supersedes is not None and row.status is MemoryStatus.ACTIVE:
            self.set_status(supersedes, MemoryStatus.SUPERSEDED, reason=f"superseded by {row.memory_id}")
        return row

    def get(self, memory_id: str) -> MemoryEntry:
        for row in self._entries:
            if row.memory_id == str(memory_id):
                return row
        raise KeyError(f"unknown memory id: {memory_id}")

    def _replace(self, row: MemoryEntry) -> MemoryEntry:
        index = row.sequence - 1
        if index < 0 or index >= len(self._entries) or self._entries[index].memory_id != row.memory_id:
            raise ValueError("memory sequence/index invariant violated")
        self._entries[index] = row
        return row

    def set_status(self, memory_id: str, status: MemoryStatus, *, reason: str) -> MemoryEntry:
        old = self.get(memory_id)
        status = MemoryStatus(status)
        if status is not MemoryStatus.ACTIVE and not str(reason).strip():
            raise ValueError("inactive memory state requires a reason")
        return self._replace(
            replace(
                old,
                status=status,
                status_reason=None if status is MemoryStatus.ACTIVE else str(reason),
            )
        )

    def read_scope(self, scope: MemoryScope, *, include_inactive: bool = False) -> tuple[MemoryEntry, ...]:
        scope = MemoryScope(scope)
        return tuple(
            row
            for row in self._entries
            if row.scope is scope and (include_inactive or row.status is MemoryStatus.ACTIVE)
        )

    def read_personal(self, agent_id: str, *, include_inactive: bool = False) -> tuple[MemoryEntry, ...]:
        return tuple(
            row
            for row in self._entries
            if row.scope is MemoryScope.PERSONAL
            and row.owner_agent_id == str(agent_id)
            and (include_inactive or row.status is MemoryStatus.ACTIVE)
        )

    def visible_entries(
        self,
        *,
        agent_id: str,
        region: str,
        task_id: str | None = None,
        include_inactive: bool = False,
    ) -> tuple[MemoryEntry, ...]:
        agent_id = str(agent_id)
        rows: list[MemoryEntry] = []
        for row in self._entries:
            if not include_inactive and row.status is not MemoryStatus.ACTIVE:
                continue
            visible = False
            if row.scope is MemoryScope.GLOBAL:
                visible = True
            elif row.scope is MemoryScope.REGION:
                visible = row.region == region
            elif row.scope is MemoryScope.PERSONAL:
                visible = row.owner_agent_id == agent_id
            elif row.scope is MemoryScope.TASK:
                visible = task_id is not None and row.task_id == str(task_id)
            elif row.scope is MemoryScope.PRIVATE:
                visible = row.owner_agent_id == agent_id
            if visible:
                rows.append(row)
        return tuple(rows)

    def retrieve(
        self,
        *,
        agent_id: str,
        region: str,
        task_id: str | None = None,
        tags: tuple[str, ...] = (),
        limit: int | None = None,
        include_inactive: bool = False,
    ) -> tuple[MemoryEntry, ...]:
        rows = list(
            self.visible_entries(
                agent_id=agent_id,
                region=region,
                task_id=task_id,
                include_inactive=include_inactive,
            )
        )
        wanted = {str(tag) for tag in tags}
        if wanted:
            rows.sort(
                key=lambda row: (
                    len(wanted.intersection(row.tags)),
                    row.status is MemoryStatus.ACTIVE,
                    row.confidence,
                    row.sequence,
                ),
                reverse=True,
            )
        else:
            rows.sort(key=lambda row: row.sequence)
        if limit is not None:
            if limit < 0:
                raise ValueError("memory retrieval limit must be non-negative")
            rows = rows[: int(limit)]
        return tuple(rows)

    def promote(self, memory_id: str, new_scope: MemoryScope, *, promotion_receipt_id: str) -> MemoryEntry:
        source = self.get(memory_id)
        new_scope = MemoryScope(new_scope)
        if source.status is not MemoryStatus.ACTIVE:
            raise PermissionError("inactive memory cannot be promoted")
        if new_scope not in (MemoryScope.PERSONAL, MemoryScope.REGION, MemoryScope.GLOBAL):
            raise ValueError("memory promotion target must be personal, regional, or global")
        if not str(promotion_receipt_id).strip():
            raise ValueError("memory promotion requires a verification receipt")
        if new_scope is MemoryScope.REGION and source.region is None:
            raise ValueError("regional promotion requires source region provenance")
        return self.write(
            new_scope,
            source.text,
            owner_agent_id=source.owner_agent_id,
            region=source.region if new_scope is MemoryScope.REGION else None,
            tags=source.tags,
            parent_memory_id=source.memory_id,
            promotion_receipt_id=str(promotion_receipt_id),
            evidence_ids=source.evidence_ids,
            confidence=source.confidence,
            dependencies=source.dependencies,
        )

    def to_state(self) -> dict[str, Any]:
        return {"entries": [row.to_state() for row in self._entries]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "MemoryFabric":
        fabric = cls()
        fabric._entries = [MemoryEntry.from_state(row) for row in state.get("entries", ())]
        for index, row in enumerate(fabric._entries, start=1):
            if row.sequence != index or row.memory_id != f"mem-{index:08d}":
                raise ValueError("memory sequence is not canonical")
        return fabric


__all__ = (
    "MemoryScope",
    "MemoryStatus",
    "MemoryEntry",
    "MemoryFabric",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
