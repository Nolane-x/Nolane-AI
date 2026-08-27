from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


ROOT = Path(__file__).resolve().parents[1]


def test_wave5c_memory_fabric_is_canonical_native_and_versioned() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["external.memory.fabric"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.memory.fabric"
    assert row.canonical_write_authority is True
    assert row.component_version == "0.0.1"
    assert str(component_version("external.memory.fabric")) == "0.0.1"


def test_wave5c_memory_fabric_is_removed_from_active_facades_only() -> None:
    facade_ids = {row.component_id for row in build_active_facade_bindings()}
    assert "external.memory.fabric" not in facade_ids


def test_wave5c_legacy_memory_schema_and_fabric_bridge_to_canonical_identity() -> None:
    from cogcoder.organization.memory import MemoryFabric as LegacyMemoryFabric
    from cogcoder.organization.types import MemoryEntry as LegacyMemoryEntry
    from cogcoder.organization.types import MemoryScope as LegacyMemoryScope
    from cogcoder.organization.types import MemoryStatus as LegacyMemoryStatus
    from nolane.memory.fabric import MemoryEntry, MemoryFabric, MemoryScope, MemoryStatus

    assert LegacyMemoryScope is MemoryScope
    assert LegacyMemoryStatus is MemoryStatus
    assert LegacyMemoryEntry is MemoryEntry
    assert LegacyMemoryFabric is MemoryFabric

    assert MemoryScope.__module__ == "nolane.memory.fabric"
    assert MemoryStatus.__module__ == "nolane.memory.fabric"
    assert MemoryEntry.__module__ == "nolane.memory.fabric"
    assert MemoryFabric.__module__ == "nolane.memory.fabric"


def test_wave5c_canonical_memory_fabric_has_no_reverse_historical_imports() -> None:
    import nolane.memory.fabric as fabric

    source = inspect.getsource(fabric)
    assert "from cogcoder.organization.memory import" not in source
    assert "import cogcoder.organization.memory" not in source
    assert "from cogcoder.organization.types import" not in source
    assert "import cogcoder.organization.types" not in source


def test_wave5c_memory_schema_preserves_values_validation_and_round_trip() -> None:
    from nolane.memory.fabric import MemoryEntry, MemoryScope, MemoryStatus

    assert tuple(row.value for row in MemoryScope) == (
        "global",
        "region",
        "personal",
        "task",
        "private",
    )
    assert tuple(row.value for row in MemoryStatus) == (
        "active",
        "stale",
        "superseded",
        "contradicted",
        "quarantined",
        "archived",
    )

    row = MemoryEntry(
        memory_id="mem-00000001",
        sequence=1,
        scope=MemoryScope.PERSONAL,
        text="verified memory",
        owner_agent_id="memory.chief",
        tags=("b", "a"),
        evidence_ids=("evidence-2", "evidence-1"),
        confidence=0.75,
        dependencies=("dep-2", "dep-1"),
    )
    assert MemoryEntry.from_state(row.to_state()) == row

    with pytest.raises(ValueError, match=r"memory confidence must lie in \[0, 1\]"):
        MemoryEntry(
            memory_id="mem-bad",
            sequence=1,
            scope=MemoryScope.PERSONAL,
            text="bad",
            owner_agent_id="memory.chief",
            confidence=1.01,
        )


def test_wave5c_memory_fabric_preserves_visibility_promotion_status_and_state() -> None:
    from nolane.memory.fabric import MemoryFabric, MemoryScope, MemoryStatus

    memory = MemoryFabric()
    global_row = memory.write(
        MemoryScope.GLOBAL,
        "global memory",
        owner_agent_id="memory.chief",
        tags=("shared", "shared"),
        evidence_ids=("evidence-b", "evidence-a", "evidence-b"),
        dependencies=("dep-b", "dep-a", "dep-b"),
    )
    personal_row = memory.write(
        MemoryScope.PERSONAL,
        "personal memory",
        owner_agent_id="memory.chief",
        region="memory-context-knowledge",
        tags=("personal",),
    )
    task_row = memory.write(
        MemoryScope.TASK,
        "task memory",
        owner_agent_id="memory.chief",
        task_id="task-1",
    )

    assert global_row.memory_id == "mem-00000001"
    assert global_row.sequence == 1
    assert global_row.tags == ("shared",)
    assert global_row.evidence_ids == ("evidence-a", "evidence-b")
    assert global_row.dependencies == ("dep-a", "dep-b")

    visible = memory.visible_entries(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        task_id="task-1",
    )
    assert tuple(row.memory_id for row in visible) == (
        global_row.memory_id,
        personal_row.memory_id,
        task_row.memory_id,
    )

    promoted = memory.promote(
        personal_row.memory_id,
        MemoryScope.REGION,
        promotion_receipt_id="promotion-00000001",
    )
    assert promoted.parent_memory_id == personal_row.memory_id
    assert promoted.promotion_receipt_id == "promotion-00000001"
    assert promoted.region == "memory-context-knowledge"

    stale = memory.set_status(global_row.memory_id, MemoryStatus.STALE, reason="superseded evidence")
    assert stale.status is MemoryStatus.STALE
    assert stale.status_reason == "superseded evidence"

    restored = MemoryFabric.from_state(memory.to_state())
    assert restored.to_state() == memory.to_state()


def test_wave5c_memory_fabric_preserves_fail_closed_validation() -> None:
    from nolane.memory.fabric import MemoryFabric, MemoryScope, MemoryStatus

    memory = MemoryFabric()
    with pytest.raises(ValueError, match="memory text must be non-empty"):
        memory.write(MemoryScope.PERSONAL, "", owner_agent_id="memory.chief")
    with pytest.raises(ValueError, match="regional memory requires a region"):
        memory.write(MemoryScope.REGION, "x", owner_agent_id="memory.chief")
    with pytest.raises(ValueError, match="task memory requires a task id"):
        memory.write(MemoryScope.TASK, "x", owner_agent_id="memory.chief")

    row = memory.write(MemoryScope.PERSONAL, "x", owner_agent_id="memory.chief")
    with pytest.raises(ValueError, match="inactive memory state requires a reason"):
        memory.set_status(row.memory_id, MemoryStatus.ARCHIVED, reason="")
    with pytest.raises(ValueError, match="memory retrieval limit must be non-negative"):
        memory.retrieve(
            agent_id="memory.chief",
            region="memory-context-knowledge",
            limit=-1,
        )


def test_wave5c_debt_reduces_only_memory_fabric_facade() -> None:
    ledger = build_component_implementation_ledger()
    counts: dict[str, int] = {}
    non_native = []
    for row in ledger.values():
        if row.status is ImplementationStatus.CANONICAL_NATIVE:
            continue
        non_native.append(row)
        counts[row.status.value] = counts.get(row.status.value, 0) + 1

    assert len(non_native) <= 42
    assert ledger["external.memory.fabric"].status is ImplementationStatus.CANONICAL_NATIVE
    assert all(row.component_id != "external.memory.fabric" for row in non_native)


def test_wave5c_acceptance_has_no_write_enabled_bootstrap_workflow() -> None:
    bootstrap = ROOT / ".github" / "workflows" / "refoundation-wave5c-bootstrap.yml"
    assert not bootstrap.exists(), "temporary write-enabled Wave-5C bootstrap must be removed before acceptance"
