from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any, Mapping

from cogcoder.organization.types import canonical_digest
from nolane.memory.fabric import MemoryEntry, MemoryFabric, MemoryStatus
from nolane.memory.lifecycle import MemoryRelationGraph


COMPONENT_ID = "external.memory.retrieval"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.memory_retrieval"


@dataclass(frozen=True, slots=True)
class MemoryRetrievalBudget:
    max_memories: int
    max_estimated_units: int

    def __post_init__(self) -> None:
        if int(self.max_memories) < 1 or int(self.max_estimated_units) < 1:
            raise ValueError('memory retrieval budget values must be positive')

    def to_state(self) -> dict[str, int]:
        return {
            'max_memories': int(self.max_memories),
            'max_estimated_units': int(self.max_estimated_units),
        }


@dataclass(frozen=True, slots=True)
class MemorySelectionReceipt:
    receipt_id: str
    agent_id: str
    region: str
    task_id: str | None
    tags: tuple[str, ...]
    budget: MemoryRetrievalBudget
    candidate_memory_ids: tuple[str, ...]
    selected_memory_ids: tuple[str, ...]
    dropped_memory_ids: tuple[str, ...]
    drop_reasons: tuple[str, ...]
    score_summary: tuple[tuple[str, int], ...]
    candidate_units: int
    selected_units: int
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'receipt_id': self.receipt_id,
            'agent_id': self.agent_id,
            'region': self.region,
            'task_id': self.task_id,
            'tags': list(self.tags),
            'budget': self.budget.to_state(),
            'candidate_memory_ids': list(self.candidate_memory_ids),
            'selected_memory_ids': list(self.selected_memory_ids),
            'dropped_memory_ids': list(self.dropped_memory_ids),
            'drop_reasons': list(self.drop_reasons),
            'score_summary': [[memory_id, score] for memory_id, score in self.score_summary],
            'candidate_units': self.candidate_units,
            'selected_units': self.selected_units,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'MemorySelectionReceipt':
        budget_state = state.get('budget', {})
        row = cls(
            receipt_id=str(state['receipt_id']),
            agent_id=str(state['agent_id']),
            region=str(state['region']),
            task_id=None if state.get('task_id') is None else str(state['task_id']),
            tags=tuple(str(value) for value in state.get('tags', ())),
            budget=MemoryRetrievalBudget(
                max_memories=int(budget_state['max_memories']),
                max_estimated_units=int(budget_state['max_estimated_units']),
            ),
            candidate_memory_ids=tuple(str(value) for value in state.get('candidate_memory_ids', ())),
            selected_memory_ids=tuple(str(value) for value in state.get('selected_memory_ids', ())),
            dropped_memory_ids=tuple(str(value) for value in state.get('dropped_memory_ids', ())),
            drop_reasons=tuple(str(value) for value in state.get('drop_reasons', ())),
            score_summary=tuple((str(value[0]), int(value[1])) for value in state.get('score_summary', ())),
            candidate_units=int(state.get('candidate_units', 0)),
            selected_units=int(state.get('selected_units', 0)),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('memory selection receipt digest mismatch')
        return row


class MemoryRetrievalEngine:
    def __init__(
        self,
        *,
        memory: MemoryFabric,
        relations: MemoryRelationGraph | None = None,
        receipts: tuple[MemorySelectionReceipt, ...] = (),
        counter: int = 0,
    ) -> None:
        self.memory = memory
        self.relations = relations
        self._receipts: dict[str, MemorySelectionReceipt] = {row.receipt_id: row for row in receipts}
        self._counter = int(counter)

    @staticmethod
    def estimate_units(row: MemoryEntry) -> int:
        textual = len(row.text) + sum(len(tag) for tag in row.tags)
        provenance = 8 * (len(row.evidence_ids) + len(row.dependencies))
        return max(1, ceil((textual + provenance + 24) / 4))

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def receipt(self, receipt_id: str) -> MemorySelectionReceipt:
        try:
            return self._receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f'unknown memory selection receipt: {receipt_id}') from exc

    def _visible_active(
        self,
        *,
        agent_id: str,
        region: str,
        task_id: str | None,
    ) -> tuple[MemoryEntry, ...]:
        rows = self.memory.visible_entries(
            agent_id=str(agent_id), region=str(region), task_id=task_id, include_inactive=False,
        )
        return tuple(row for row in rows if row.status is MemoryStatus.ACTIVE)

    def _score(
        self,
        row: MemoryEntry,
        *,
        task_id: str | None,
        tags: set[str],
        visible_ids: set[str],
    ) -> int:
        score = 0
        if task_id is not None and row.task_id == str(task_id):
            score += 1000
        score += 100 * len(tags.intersection(row.tags))
        if row.evidence_ids:
            score += 20
        score += int(round(float(row.confidence) * 50))
        score += min(20, len(row.dependencies) * 5)
        if self.relations is not None:
            relation_count = 0
            for relation in self.relations.for_memory(row.memory_id):
                other = relation.target_memory_id if relation.source_memory_id == row.memory_id else relation.source_memory_id
                if other in visible_ids:
                    relation_count += 1
            score += min(25, relation_count * 5)
        return score

    def select(
        self,
        *,
        agent_id: str,
        region: str,
        task_id: str | None,
        tags: tuple[str, ...],
        budget: MemoryRetrievalBudget,
    ) -> MemorySelectionReceipt:
        normalized_tags = tuple(sorted({str(tag) for tag in tags if str(tag).strip()}))
        tag_set = set(normalized_tags)
        candidates = self._visible_active(
            agent_id=str(agent_id), region=str(region), task_id=task_id,
        )
        visible_ids = {row.memory_id for row in candidates}
        scored = [
            (row, self._score(row, task_id=task_id, tags=tag_set, visible_ids=visible_ids), self.estimate_units(row))
            for row in candidates
        ]
        scored.sort(key=lambda value: (-value[1], -value[0].sequence, value[0].memory_id))

        selected: list[str] = []
        dropped: list[str] = []
        drop_reasons: list[str] = []
        selected_units = 0
        for row, _, units in scored:
            if len(selected) >= budget.max_memories:
                dropped.append(row.memory_id)
                drop_reasons.append(f'{row.memory_id}:max_memories')
                continue
            if selected_units + units > budget.max_estimated_units:
                dropped.append(row.memory_id)
                drop_reasons.append(f'{row.memory_id}:unit_budget')
                continue
            selected.append(row.memory_id)
            selected_units += units

        self._counter += 1
        receipt_id = f'memory-selection-{self._counter:08d}'
        candidate_ids = tuple(row.memory_id for row, _, _ in scored)
        score_summary = tuple((row.memory_id, score) for row, score, _ in scored)
        candidate_units = sum(units for _, _, units in scored)
        payload = {
            'receipt_id': receipt_id,
            'agent_id': str(agent_id),
            'region': str(region),
            'task_id': None if task_id is None else str(task_id),
            'tags': list(normalized_tags),
            'budget': budget.to_state(),
            'candidate_memory_ids': list(candidate_ids),
            'selected_memory_ids': list(selected),
            'dropped_memory_ids': list(dropped),
            'drop_reasons': list(drop_reasons),
            'score_summary': [[memory_id, score] for memory_id, score in score_summary],
            'candidate_units': candidate_units,
            'selected_units': selected_units,
        }
        receipt = MemorySelectionReceipt(
            receipt_id=receipt_id,
            agent_id=str(agent_id),
            region=str(region),
            task_id=None if task_id is None else str(task_id),
            tags=normalized_tags,
            budget=budget,
            candidate_memory_ids=candidate_ids,
            selected_memory_ids=tuple(selected),
            dropped_memory_ids=tuple(dropped),
            drop_reasons=tuple(drop_reasons),
            score_summary=score_summary,
            candidate_units=candidate_units,
            selected_units=selected_units,
            digest=canonical_digest(payload),
        )
        self._receipts[receipt.receipt_id] = receipt
        return receipt

    def selected_entries(self, receipt: MemorySelectionReceipt | str) -> tuple[MemoryEntry, ...]:
        row = self.receipt(receipt) if isinstance(receipt, str) else receipt
        return tuple(self.memory.get(memory_id) for memory_id in row.selected_memory_ids)

    def to_state(self) -> dict[str, Any]:
        return {
            'receipts': [self._receipts[key].to_state() for key in sorted(self._receipts)],
            'counter': self._counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        memory: MemoryFabric,
        relations: MemoryRelationGraph | None,
        state: Mapping[str, Any],
    ) -> 'MemoryRetrievalEngine':
        receipts = tuple(MemorySelectionReceipt.from_state(row) for row in state.get('receipts', ()))
        result = cls(
            memory=memory,
            relations=relations,
            receipts=receipts,
            counter=int(state.get('counter', len(receipts))),
        )
        for receipt in receipts:
            for memory_id in receipt.candidate_memory_ids:
                memory.get(memory_id)
        return result


__all__ = (
    "MemoryRetrievalBudget",
    "MemorySelectionReceipt",
    "MemoryRetrievalEngine",
)
