from __future__ import annotations

import inspect

import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.types import AgentStatus, EventKind
from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger


NATIVE_TASK_CONTROL = {
    "organization.tasks": "nolane.organization.tasks",
    "organization.lifecycle": "nolane.organization.lifecycle",
    "organization.coordination.leases": "nolane.organization.coordination_leases",
    "organization.coordination.delivery": "nolane.organization.coordination_delivery",
    "organization.coordination.conflicts": "nolane.organization.coordination_conflicts",
    "organization.coordination": "nolane.organization.coordination",
}


def _substrate():
    from nolane.organization.authority import AuthorityGraph
    from nolane.organization.events import EventLedger
    from nolane.organization.identity import AgentRegistry

    registry = AgentRegistry(build_first_generation_blueprint())
    events = EventLedger()
    authority = AuthorityGraph(registry)
    authority.claim_owner("master-plan", "planning.chief")
    return registry, events, authority


def test_task_control_components_are_native_and_independently_versioned() -> None:
    ledger = build_component_implementation_ledger()
    for component_id, module in NATIVE_TASK_CONTROL.items():
        row = ledger[component_id]
        assert row.status is ImplementationStatus.CANONICAL_NATIVE
        assert row.canonical_module == module
        assert row.canonical_write_authority
        assert row.component_version == "0.0.1"
        assert str(component_version(component_id)) == "0.0.1"


def test_task_lifecycle_coordination_are_not_compatibility_facades() -> None:
    facade_ids = {row.component_id for row in build_active_facade_bindings()}
    assert {"organization.tasks", "organization.lifecycle", "organization.coordination"}.isdisjoint(facade_ids)


def test_legacy_task_control_modules_bridge_to_canonical_class_identity() -> None:
    from cogcoder.organization.coordination import CoordinationControlPlane as LegacyCoordination
    from cogcoder.organization.coordination_conflicts import ConflictCoordinator as LegacyConflicts
    from cogcoder.organization.coordination_delivery import DeliveryCoordinator as LegacyDelivery
    from cogcoder.organization.coordination_leases import LeaseCoordinator as LegacyLeases
    from cogcoder.organization.scheduler import WakeSleepScheduler as LegacyScheduler
    from cogcoder.organization.tasks import TaskGraph as LegacyTaskGraph, TaskRecord as LegacyTaskRecord
    from nolane.organization.coordination import CoordinationControlPlane
    from nolane.organization.coordination_conflicts import ConflictCoordinator
    from nolane.organization.coordination_delivery import DeliveryCoordinator
    from nolane.organization.coordination_leases import LeaseCoordinator
    from nolane.organization.lifecycle import WakeSleepScheduler
    from nolane.organization.tasks import TaskGraph, TaskRecord

    assert LegacyTaskGraph is TaskGraph
    assert LegacyTaskRecord is TaskRecord
    assert LegacyScheduler is WakeSleepScheduler
    assert LegacyLeases is LeaseCoordinator
    assert LegacyDelivery is DeliveryCoordinator
    assert LegacyConflicts is ConflictCoordinator
    assert LegacyCoordination is CoordinationControlPlane
    assert TaskGraph.__module__ == "nolane.organization.tasks"
    assert WakeSleepScheduler.__module__ == "nolane.organization.lifecycle"
    assert LeaseCoordinator.__module__ == "nolane.organization.coordination_leases"
    assert DeliveryCoordinator.__module__ == "nolane.organization.coordination_delivery"
    assert ConflictCoordinator.__module__ == "nolane.organization.coordination_conflicts"
    assert CoordinationControlPlane.__module__ == "nolane.organization.coordination"


def test_native_task_control_modules_never_import_historical_implementations() -> None:
    import nolane.organization.coordination as coordination
    import nolane.organization.coordination_conflicts as conflicts
    import nolane.organization.coordination_delivery as delivery
    import nolane.organization.coordination_leases as leases
    import nolane.organization.lifecycle as lifecycle
    import nolane.organization.tasks as tasks

    forbidden = "cogcoder.organization."
    for module in (tasks, lifecycle, leases, delivery, conflicts, coordination):
        source = inspect.getsource(module)
        # Shared type schemas may remain under cogcoder.organization.types during Epoch 0,
        # but a canonical implementation may not import an old behavior module.
        behavior_imports = [line for line in source.splitlines() if "import" in line and forbidden in line]
        assert all("cogcoder.organization.types" in line for line in behavior_imports)


def test_native_task_graph_preserves_cycle_lease_completion_and_round_trip() -> None:
    from nolane.organization.tasks import TaskGraph

    registry, events, authority = _substrate()
    graph = TaskGraph(ledger=events, registry=registry, authority=authority)
    graph.add_task("task-a", title="A", plan_node_id="plan-a")
    graph.add_task("task-b", title="B", plan_node_id="plan-b")
    graph.add_dependency("task-b", "task-a")
    with pytest.raises(ValueError):
        graph.add_dependency("task-a", "task-b")

    graph.lease("task-a", "coding.backend.01")
    completed = graph.complete("task-a", "coding.backend.01", output_artifact_ids=("artifact-a",))
    assert completed.completed_by == "coding.backend.01"
    assert registry.get("coding.backend.01").current_task is None
    assert events.events_since(None)[-1].kind is EventKind.TASK_COMPLETED

    restored = TaskGraph.from_state(graph.to_state(), ledger=events, registry=registry, authority=authority)
    assert restored.to_state() == graph.to_state()


def test_native_lifecycle_preserves_checkpoint_wake_and_round_trip() -> None:
    from nolane.organization.lifecycle import WakeSleepScheduler

    registry, events, _ = _substrate()
    scheduler = WakeSleepScheduler(registry=registry, ledger=events)
    agent_id = "coding.backend.01"
    scheduler.sleep(agent_id)
    assert registry.get(agent_id).status is AgentStatus.SLEEPING
    checkpoint = scheduler.checkpoint_for(agent_id)
    assert checkpoint is not None

    scheduler.schedule_periodic_wake(agent_id, token=5)
    scheduler.tick(5)
    assert agent_id in scheduler.due_agents()
    scheduler.wake(agent_id, reason="wave2b-test")
    assert registry.get(agent_id).status is AgentStatus.ACTIVE

    state = scheduler.to_state()
    restored = WakeSleepScheduler.from_state(registry=registry, ledger=events, state=state)
    assert restored.to_state() == state


def test_native_lease_coordinator_preserves_epoch_fencing_stale_detection_and_round_trip() -> None:
    from nolane.organization.coordination_leases import LeaseCoordinator, LeaseStatus
    from nolane.organization.tasks import TaskGraph

    registry, events, authority = _substrate()
    tasks = TaskGraph(ledger=events, registry=registry, authority=authority)
    tasks.add_task("lease-task", title="Lease", plan_node_id="lease-plan")
    leases = LeaseCoordinator(registry=registry, tasks=tasks, events=events)

    first = leases.grant("lease-task", "coding.backend.01", token=1, stale_after_tokens=3)
    assert first.status is LeaseStatus.ACTIVE
    renewed = leases.heartbeat("lease-task", "coding.backend.01", lease_id=first.lease_id, epoch=first.epoch, token=2)
    assert renewed.renewal_count == 1
    with pytest.raises(PermissionError):
        leases.heartbeat("lease-task", "coding.backend.01", lease_id=first.lease_id, epoch=first.epoch + 1, token=3)

    stale = leases.detect_stale(5)
    assert stale and stale[0].lease_id == first.lease_id
    restored = LeaseCoordinator.from_state(registry=registry, tasks=tasks, events=events, state=leases.to_state())
    assert restored.to_state() == leases.to_state()


def test_native_delivery_coordinator_preserves_causal_order_ack_and_round_trip() -> None:
    from nolane.organization.coordination_delivery import AckStatus, DeliveryCoordinator

    registry, events, _ = _substrate()
    delivery = DeliveryCoordinator(registry=registry, events=events)
    parent = events.append(
        EventKind.TASK_PROGRESS,
        source_agent_id="coding.backend.01",
        target_agent_id="coding.chief",
        requires_ack=True,
    )
    child = events.append(
        EventKind.TASK_PROGRESS,
        source_agent_id="coding.backend.01",
        target_agent_id="coding.chief",
        causal_parent_ids=(parent.event_id,),
    )
    with pytest.raises(ValueError):
        delivery.deliver(child.event_id, "coding.chief")
    receipt = delivery.deliver(parent.event_id, "coding.chief")
    assert receipt.ack_status is AckStatus.PENDING
    acked = delivery.acknowledge(receipt.delivery_id, "coding.chief")
    assert acked.ack_status is AckStatus.ACKED
    delivery.deliver(child.event_id, "coding.chief")

    restored = DeliveryCoordinator.from_state(registry=registry, events=events, state=delivery.to_state())
    assert restored.to_state() == delivery.to_state()


def test_native_conflict_coordinator_preserves_owner_authority_and_round_trip() -> None:
    from nolane.organization.coordination_conflicts import ConflictCoordinator, ConflictStatus

    registry, events, authority = _substrate()
    authority.claim_owner("artifact-conflict", "coding.chief")
    conflicts = ConflictCoordinator(registry=registry, authority=authority, events=events)
    packet = conflicts.open(
        "debug.chief",
        "artifact-conflict",
        proposition="patch is unsafe",
        requested_action="block merge",
        evidence_refs=("evidence-conflict",),
    )
    assert packet.status is ConflictStatus.OPEN
    conflicts.add_claim(
        packet.conflict_id,
        "coding.chief",
        proposition="patch is safe",
        requested_action="merge",
        evidence_refs=("evidence-owner",),
    )
    resolution = conflicts.resolve(
        packet.conflict_id,
        "coding.chief",
        decision="merge after verification",
        evidence_refs=("evidence-resolution",),
    )
    assert conflicts.get(packet.conflict_id).status is ConflictStatus.RESOLVED
    assert resolution.resolver_agent_id == "coding.chief"

    restored = ConflictCoordinator.from_state(
        registry=registry, authority=authority, events=events, state=conflicts.to_state()
    )
    assert restored.to_state() == conflicts.to_state()
