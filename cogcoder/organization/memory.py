from __future__ import annotations

from typing import Any, Mapping

from .types import MemoryEntry, MemoryScope


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
    ) -> MemoryEntry:
        scope = MemoryScope(scope)
        if not str(text).strip():
            raise ValueError('memory text must be non-empty')
        if not str(owner_agent_id).strip():
            raise ValueError('memory owner must be explicit')
        if scope is MemoryScope.REGION and not region:
            raise ValueError('regional memory requires a region')
        if scope is MemoryScope.TASK and not task_id:
            raise ValueError('task memory requires a task id')
        sequence = len(self._entries) + 1
        row = MemoryEntry(
            memory_id=f'mem-{sequence:08d}',
            sequence=sequence,
            scope=scope,
            text=str(text),
            owner_agent_id=str(owner_agent_id),
            region=None if region is None else str(region),
            task_id=None if task_id is None else str(task_id),
            tags=tuple(sorted({str(tag) for tag in tags})),
            parent_memory_id=None if parent_memory_id is None else str(parent_memory_id),
            promotion_receipt_id=None if promotion_receipt_id is None else str(promotion_receipt_id),
        )
        self._entries.append(row)
        return row

    def get(self, memory_id: str) -> MemoryEntry:
        for row in self._entries:
            if row.memory_id == str(memory_id):
                return row
        raise KeyError(f'unknown memory id: {memory_id}')

    def read_scope(self, scope: MemoryScope) -> tuple[MemoryEntry, ...]:
        scope = MemoryScope(scope)
        return tuple(row for row in self._entries if row.scope is scope)

    def read_personal(self, agent_id: str) -> tuple[MemoryEntry, ...]:
        return tuple(
            row
            for row in self._entries
            if row.scope is MemoryScope.PERSONAL and row.owner_agent_id == str(agent_id)
        )

    def visible_entries(self, *, agent_id: str, region: str, task_id: str | None = None) -> tuple[MemoryEntry, ...]:
        agent_id = str(agent_id)
        rows: list[MemoryEntry] = []
        for row in self._entries:
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
    ) -> tuple[MemoryEntry, ...]:
        rows = list(self.visible_entries(agent_id=agent_id, region=region, task_id=task_id))
        wanted = {str(tag) for tag in tags}
        if wanted:
            rows.sort(key=lambda row: (len(wanted.intersection(row.tags)), row.sequence), reverse=True)
        else:
            rows.sort(key=lambda row: row.sequence)
        if limit is not None:
            if limit < 0:
                raise ValueError('memory retrieval limit must be non-negative')
            rows = rows[: int(limit)]
        return tuple(rows)

    def promote(self, memory_id: str, new_scope: MemoryScope, *, promotion_receipt_id: str) -> MemoryEntry:
        source = self.get(memory_id)
        new_scope = MemoryScope(new_scope)
        if new_scope not in (MemoryScope.PERSONAL, MemoryScope.REGION, MemoryScope.GLOBAL):
            raise ValueError('memory promotion target must be personal, regional, or global')
        if not str(promotion_receipt_id).strip():
            raise ValueError('memory promotion requires a verification receipt')
        if new_scope is MemoryScope.REGION and source.region is None:
            raise ValueError('regional promotion requires source region provenance')
        return self.write(
            new_scope,
            source.text,
            owner_agent_id=source.owner_agent_id,
            region=source.region if new_scope is MemoryScope.REGION else None,
            tags=source.tags,
            parent_memory_id=source.memory_id,
            promotion_receipt_id=str(promotion_receipt_id),
        )

    def to_state(self) -> dict[str, Any]:
        return {'entries': [row.to_state() for row in self._entries]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'MemoryFabric':
        fabric = cls()
        fabric._entries = [MemoryEntry.from_state(row) for row in state.get('entries', ())]
        for index, row in enumerate(fabric._entries, start=1):
            if row.sequence != index or row.memory_id != f'mem-{index:08d}':
                raise ValueError('memory sequence is not canonical')
        return fabric
