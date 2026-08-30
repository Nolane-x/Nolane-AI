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


class _RegistryStub:
    def __init__(self) -> None:
        self._actors = {
            "memory.chief": SimpleNamespace(
                agent_id="memory.chief",
                region="memory-context-knowledge",
            ),
            "memory.worker": SimpleNamespace(
                agent_id="memory.worker",
                region="memory-context-knowledge",
            ),
            "outsider": SimpleNamespace(
                agent_id="outsider",
                region="coding-implementation",
            ),
        }

    def get(self, agent_id: str):
        try:
            return self._actors[str(agent_id)]
        except KeyError as exc:
            raise KeyError(f"unknown actor: {agent_id}") from exc


class _EventStub:
    def __init__(self) -> None:
        self._known: set[str] = set()
        self._latest: str | None = None

    def latest_event_id(self) -> str | None:
        return self._latest

    def get(self, event_id: str):
        if str(event_id) not in self._known:
            raise KeyError(f"unknown event: {event_id}")
        return SimpleNamespace(event_id=str(event_id))


def test_wave5d_memory_lifecycle_is_canonical_native_and_versioned() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger["external.memory.lifecycle"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.memory.lifecycle"
    assert row.canonical_write_authority is True
    assert row.component_version == "0.0.3"
    assert str(component_version("external.memory.lifecycle")) == "0.0.3"


def test_wave5d_memory_lifecycle_leaves_facades_but_retrieval_does_not() -> None:
    facade_ids = {row.component_id for row in build_active_facade_bindings()}
    assert "external.memory.lifecycle" not in facade_ids


def test_wave5d_all_legacy_lifecycle_objects_bridge_to_canonical_identity() -> None:
    from cogcoder.organization.memory_lifecycle import (
        MemoryLifecycleLedger as LegacyLedger,
        MemoryLifecycleReceipt as LegacyReceipt,
        MemoryRelation as LegacyRelation,
        MemoryRelationGraph as LegacyGraph,
        MemoryRelationKind as LegacyKind,
    )
    from nolane.memory.lifecycle import (
        MemoryLifecycleLedger,
        MemoryLifecycleReceipt,
        MemoryRelation,
        MemoryRelationGraph,
        MemoryRelationKind,
    )

    pairs = (
        (LegacyReceipt, MemoryLifecycleReceipt),
        (LegacyLedger, MemoryLifecycleLedger),
        (LegacyKind, MemoryRelationKind),
        (LegacyRelation, MemoryRelation),
        (LegacyGraph, MemoryRelationGraph),
    )
    for legacy, canonical in pairs:
        assert legacy is canonical
        assert canonical.__module__ == "nolane.memory.lifecycle"


def test_wave5d_canonical_lifecycle_has_no_reverse_import_to_historical_owner() -> None:
    import nolane.memory.lifecycle as lifecycle

    source = inspect.getsource(lifecycle)
    assert "from cogcoder.organization.memory_lifecycle import" not in source
    assert "import cogcoder.organization.memory_lifecycle" not in source


def test_wave5d_lifecycle_preserves_transition_authority_digests_and_restore() -> None:
    from nolane.memory.fabric import MemoryFabric, MemoryScope, MemoryStatus
    from nolane.memory.lifecycle import MemoryLifecycleLedger, MemoryLifecycleReceipt

    registry = _RegistryStub()
    events = _EventStub()
    memory = MemoryFabric()
    row = memory.write(
        MemoryScope.PERSONAL,
        "governed memory",
        owner_agent_id="memory.chief",
    )
    ledger = MemoryLifecycleLedger(registry=registry, memory=memory, events=events)

    stale = ledger.transition(
        row.memory_id,
        actor_agent_id="memory.worker",
        new_status=MemoryStatus.STALE,
        reason="evidence aged",
        evidence_refs=("evidence-1",),
    )
    assert stale.receipt_id == "memory-lifecycle-00000001"
    assert stale.previous_status is MemoryStatus.ACTIVE
    assert stale.new_status is MemoryStatus.STALE
    assert MemoryLifecycleReceipt.from_state(stale.to_state()) == stale
    assert memory.get(row.memory_id).status is MemoryStatus.STALE

    with pytest.raises(PermissionError, match="Memory Chief authority"):
        ledger.transition(
            row.memory_id,
            actor_agent_id="memory.worker",
            new_status=MemoryStatus.ACTIVE,
            reason="corrected",
            evidence_refs=("evidence-2",),
            correction_ref="correction-1",
        )
    with pytest.raises(ValueError, match="corrective reference"):
        ledger.transition(
            row.memory_id,
            actor_agent_id="memory.chief",
            new_status=MemoryStatus.ACTIVE,
            reason="corrected",
            evidence_refs=("evidence-2",),
        )
    with pytest.raises(PermissionError, match="Memory/Context identity"):
        ledger.transition(
            row.memory_id,
            actor_agent_id="outsider",
            new_status=MemoryStatus.ARCHIVED,
            reason="not authorized",
            evidence_refs=("evidence-3",),
        )

    active = ledger.transition(
        row.memory_id,
        actor_agent_id="memory.chief",
        new_status=MemoryStatus.ACTIVE,
        reason="corrective evidence accepted",
        evidence_refs=("evidence-2",),
        correction_ref="correction-1",
    )
    assert active.receipt_id == "memory-lifecycle-00000002"
    assert memory.get(row.memory_id).status is MemoryStatus.ACTIVE

    restored = MemoryLifecycleLedger.from_state(
        registry=registry,
        memory=memory,
        events=events,
        state=ledger.to_state(),
    )
    assert restored.to_state() == ledger.to_state()
    assert restored.digest == ledger.digest

    corrupted = dict(active.to_state())
    corrupted["digest"] = "0" * 64
    with pytest.raises(ValueError, match="receipt digest mismatch"):
        MemoryLifecycleReceipt.from_state(corrupted)


def test_wave5d_relation_graph_preserves_idempotence_authority_and_restore() -> None:
    from nolane.memory.fabric import MemoryFabric, MemoryScope
    from nolane.memory.lifecycle import MemoryRelationGraph, MemoryRelationKind

    registry = _RegistryStub()
    events = _EventStub()
    memory = MemoryFabric()
    source = memory.write(MemoryScope.PERSONAL, "source", owner_agent_id="memory.chief")
    target = memory.write(MemoryScope.PERSONAL, "target", owner_agent_id="memory.chief")
    graph = MemoryRelationGraph(registry=registry, memory=memory, events=events)

    relation = graph.add(
        actor_agent_id="memory.worker",
        source_memory_id=source.memory_id,
        target_memory_id=target.memory_id,
        kind=MemoryRelationKind.SUPPORTS,
        evidence_refs=("evidence-1",),
    )
    assert relation.relation_id == "memory-relation-00000001"
    assert relation.kind is MemoryRelationKind.SUPPORTS
    assert graph.add(
        actor_agent_id="memory.worker",
        source_memory_id=source.memory_id,
        target_memory_id=target.memory_id,
        kind=MemoryRelationKind.SUPPORTS,
        evidence_refs=("evidence-1",),
    ) is relation

    with pytest.raises(ValueError, match="rebound to different evidence"):
        graph.add(
            actor_agent_id="memory.worker",
            source_memory_id=source.memory_id,
            target_memory_id=target.memory_id,
            kind=MemoryRelationKind.SUPPORTS,
            evidence_refs=("evidence-2",),
        )
    with pytest.raises(ValueError, match="contradict or supersede itself"):
        graph.add(
            actor_agent_id="memory.worker",
            source_memory_id=source.memory_id,
            target_memory_id=source.memory_id,
            kind=MemoryRelationKind.CONTRADICTS,
            evidence_refs=("evidence-3",),
        )
    with pytest.raises(PermissionError, match="Memory/Context identity"):
        graph.add(
            actor_agent_id="outsider",
            source_memory_id=source.memory_id,
            target_memory_id=target.memory_id,
            kind=MemoryRelationKind.DEPENDS_ON,
            evidence_refs=("evidence-4",),
        )

    restored = MemoryRelationGraph.from_state(
        registry=registry,
        memory=memory,
        events=events,
        state=graph.to_state(),
    )
    assert restored.to_state() == graph.to_state()
    assert restored.digest == graph.digest

    duplicate_state = graph.to_state()
    duplicate_state = {
        "relations": [*duplicate_state["relations"], duplicate_state["relations"][0]],
        "counter": 2,
    }
    with pytest.raises(ValueError, match="duplicate memory semantic relation"):
        MemoryRelationGraph.from_state(
            registry=registry,
            memory=memory,
            events=events,
            state=duplicate_state,
        )


def test_wave5d_inventory_preserves_lifecycle_canonical_destination() -> None:
    census = GitSnapshotInventory.capture(ROOT, FIRST_GENERATION_SNAPSHOT).to_census()
    assert (
        census.get("cogcoder/organization/memory_lifecycle.py").canonical_destination
        == "nolane/memory/lifecycle.py"
    )


def test_wave5d_debt_reduces_only_memory_lifecycle_facade() -> None:
    ledger = build_component_implementation_ledger()
    counts: dict[str, int] = {}
    non_native = []
    for row in ledger.values():
        if row.status is ImplementationStatus.CANONICAL_NATIVE:
            continue
        non_native.append(row)
        counts[row.status.value] = counts.get(row.status.value, 0) + 1

    assert len(non_native) <= 41
    assert ledger["external.memory.lifecycle"].status is ImplementationStatus.CANONICAL_NATIVE
    assert all(row.component_id != "external.memory.lifecycle" for row in non_native)
