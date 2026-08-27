from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT


ROOT = Path(__file__).resolve().parents[1]


class _RelationsStub:
    def __init__(self, linked: dict[str, tuple[str, ...]] | None = None) -> None:
        self.linked = linked or {}

    def for_memory(self, memory_id: str):
        rows = []
        for other in self.linked.get(str(memory_id), ()):
            rows.append(
                SimpleNamespace(
                    source_memory_id=str(memory_id),
                    target_memory_id=str(other),
                )
            )
        return tuple(rows)


def test_wave5e_memory_retrieval_is_canonical_native_and_versioned() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["external.memory.retrieval"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.memory.retrieval"
    assert row.canonical_write_authority is True
    assert row.component_version == "0.0.1"
    assert str(component_version("external.memory.retrieval")) == "0.0.1"


def test_wave5e_memory_retrieval_leaves_active_facades() -> None:
    facade_ids = {row.component_id for row in build_active_facade_bindings()}
    assert "external.memory.retrieval" not in facade_ids


def test_wave5e_all_legacy_retrieval_objects_bridge_to_canonical_identity() -> None:
    from cogcoder.organization.memory_retrieval import (
        MemoryRetrievalBudget as LegacyBudget,
        MemoryRetrievalEngine as LegacyEngine,
        MemorySelectionReceipt as LegacyReceipt,
    )
    from nolane.memory.retrieval import (
        MemoryRetrievalBudget,
        MemoryRetrievalEngine,
        MemorySelectionReceipt,
    )

    for legacy, canonical in (
        (LegacyBudget, MemoryRetrievalBudget),
        (LegacyReceipt, MemorySelectionReceipt),
        (LegacyEngine, MemoryRetrievalEngine),
    ):
        assert legacy is canonical
        assert canonical.__module__ == "nolane.memory.retrieval"


def test_wave5e_canonical_retrieval_has_no_reverse_import_to_historical_owner() -> None:
    import nolane.memory.retrieval as retrieval

    source = inspect.getsource(retrieval)
    assert "from cogcoder.organization.memory_retrieval import" not in source
    assert "import cogcoder.organization.memory_retrieval" not in source


def test_wave5e_budget_and_selection_receipt_preserve_fail_closed_validation() -> None:
    from nolane.memory.retrieval import MemoryRetrievalBudget, MemorySelectionReceipt

    with pytest.raises(ValueError, match="budget values must be positive"):
        MemoryRetrievalBudget(max_memories=0, max_estimated_units=10)
    with pytest.raises(ValueError, match="budget values must be positive"):
        MemoryRetrievalBudget(max_memories=1, max_estimated_units=0)

    budget = MemoryRetrievalBudget(max_memories=2, max_estimated_units=100)
    from cogcoder.organization.types import canonical_digest

    payload = {
        "receipt_id": "memory-selection-00000001",
        "agent_id": "memory.chief",
        "region": "memory-context-knowledge",
        "task_id": None,
        "tags": ["alpha"],
        "budget": budget.to_state(),
        "candidate_memory_ids": ["mem-00000001"],
        "selected_memory_ids": ["mem-00000001"],
        "dropped_memory_ids": [],
        "drop_reasons": [],
        "score_summary": [["mem-00000001", 170]],
        "candidate_units": 10,
        "selected_units": 10,
    }
    receipt = MemorySelectionReceipt.from_state({**payload, "digest": canonical_digest(payload)})
    assert receipt.to_state() == {**payload, "digest": canonical_digest(payload)}

    corrupted = receipt.to_state()
    corrupted["digest"] = "0" * 64
    with pytest.raises(ValueError, match="memory selection receipt digest mismatch"):
        MemorySelectionReceipt.from_state(corrupted)


def test_wave5e_engine_preserves_scoring_budget_drop_reasons_and_state_round_trip() -> None:
    from nolane.memory.fabric import MemoryFabric, MemoryScope
    from nolane.memory.retrieval import MemoryRetrievalBudget, MemoryRetrievalEngine, MemorySelectionReceipt

    memory = MemoryFabric()
    task = memory.write(
        MemoryScope.TASK,
        "task-specific memory",
        owner_agent_id="memory.chief",
        task_id="task-1",
        tags=("alpha",),
        evidence_ids=("evidence-1",),
        confidence=0.9,
    )
    tagged = memory.write(
        MemoryScope.PERSONAL,
        "tagged personal memory",
        owner_agent_id="memory.chief",
        tags=("alpha", "beta"),
        confidence=0.8,
        dependencies=("dep-1",),
    )
    global_row = memory.write(
        MemoryScope.GLOBAL,
        "global memory",
        owner_agent_id="memory.chief",
        confidence=0.7,
    )

    relations = _RelationsStub({tagged.memory_id: (global_row.memory_id,)})
    engine = MemoryRetrievalEngine(memory=memory, relations=relations)
    budget = MemoryRetrievalBudget(max_memories=2, max_estimated_units=10_000)
    receipt = engine.select(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        task_id="task-1",
        tags=("alpha", "alpha"),
        budget=budget,
    )

    assert receipt.receipt_id == "memory-selection-00000001"
    assert receipt.tags == ("alpha",)
    assert receipt.candidate_memory_ids[0] == task.memory_id
    assert tagged.memory_id in receipt.candidate_memory_ids
    assert receipt.selected_memory_ids == receipt.candidate_memory_ids[:2]
    assert len(receipt.dropped_memory_ids) == 1
    assert receipt.drop_reasons == (f"{receipt.dropped_memory_ids[0]}:max_memories",)
    assert receipt.selected_units <= budget.max_estimated_units
    assert MemorySelectionReceipt.from_state(receipt.to_state()) == receipt
    assert tuple(row.memory_id for row in engine.selected_entries(receipt)) == receipt.selected_memory_ids
    assert tuple(row.memory_id for row in engine.selected_entries(receipt.receipt_id)) == receipt.selected_memory_ids

    restored = MemoryRetrievalEngine.from_state(
        memory=memory,
        relations=relations,
        state=engine.to_state(),
    )
    assert restored.to_state() == engine.to_state()
    assert restored.digest == engine.digest

    tiny = MemoryRetrievalEngine(memory=memory)
    unit_budget = max(1, tiny.estimate_units(task) - 1)
    tiny_receipt = tiny.select(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        task_id="task-1",
        tags=(),
        budget=MemoryRetrievalBudget(max_memories=10, max_estimated_units=unit_budget),
    )
    assert task.memory_id in tiny_receipt.dropped_memory_ids
    assert f"{task.memory_id}:unit_budget" in tiny_receipt.drop_reasons

    with pytest.raises(KeyError, match="unknown memory selection receipt"):
        engine.receipt("missing")


def test_wave5e_relation_bonus_is_bounded_and_can_change_ranking() -> None:
    from nolane.memory.fabric import MemoryFabric, MemoryScope
    from nolane.memory.retrieval import MemoryRetrievalBudget, MemoryRetrievalEngine

    memory = MemoryFabric()
    first = memory.write(
        MemoryScope.GLOBAL,
        "first",
        owner_agent_id="memory.chief",
        confidence=0.5,
    )
    second = memory.write(
        MemoryScope.GLOBAL,
        "second",
        owner_agent_id="memory.chief",
        confidence=0.5,
    )
    third = memory.write(
        MemoryScope.GLOBAL,
        "third",
        owner_agent_id="memory.chief",
        confidence=0.5,
    )
    relations = _RelationsStub({first.memory_id: (second.memory_id, third.memory_id)})
    engine = MemoryRetrievalEngine(memory=memory, relations=relations)
    receipt = engine.select(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        task_id=None,
        tags=(),
        budget=MemoryRetrievalBudget(max_memories=3, max_estimated_units=10_000),
    )
    scores = dict(receipt.score_summary)
    assert scores[first.memory_id] - scores[second.memory_id] == 10
    assert receipt.candidate_memory_ids[0] == first.memory_id


def test_wave5e_inventory_preserves_retrieval_canonical_destination() -> None:
    census = GitSnapshotInventory.capture(ROOT, FIRST_GENERATION_SNAPSHOT).to_census()
    assert (
        census.get("cogcoder/organization/memory_retrieval.py").canonical_destination
        == "nolane/memory/retrieval.py"
    )


def test_wave5e_debt_reduces_only_memory_retrieval_facade() -> None:
    ledger = build_component_implementation_ledger()
    counts: dict[str, int] = {}
    non_native = []
    for row in ledger.values():
        if row.status is ImplementationStatus.CANONICAL_NATIVE:
            continue
        non_native.append(row)
        counts[row.status.value] = counts.get(row.status.value, 0) + 1

    assert len(non_native) <= 40
    assert ledger["external.memory.retrieval"].status is ImplementationStatus.CANONICAL_NATIVE
    assert all(row.component_id != "external.memory.retrieval" for row in non_native)
