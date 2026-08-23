from __future__ import annotations

import inspect

import pytest

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.types import AgentStatus, EventKind
from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import ImplementationStatus, build_component_implementation_ledger


CENTRAL_COMPONENT = "organization.central"
CANONICAL_MODULES = (
    "nolane.organization.central",
    "nolane.organization.central_access",
    "nolane.organization.central_conflicts",
    "nolane.organization.central_resources",
    "nolane.organization.central_state",
)


def _substrate():
    from nolane.organization.authority import AuthorityGraph
    from nolane.organization.events import EventLedger
    from nolane.organization.identity import AgentRegistry
    from nolane.organization.lifecycle import WakeSleepScheduler
    from nolane.organization.tasks import TaskGraph

    registry = AgentRegistry(build_first_generation_blueprint())
    ledger = EventLedger()
    authority = AuthorityGraph(registry)
    tasks = TaskGraph(ledger=ledger, registry=registry, authority=authority)
    scheduler = WakeSleepScheduler(registry=registry, ledger=ledger)
    return registry, ledger, authority, tasks, scheduler


def test_central_component_is_native_versioned_and_not_a_facade() -> None:
    ledger = build_component_implementation_ledger()
    row = ledger[CENTRAL_COMPONENT]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.organization.central"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version(CENTRAL_COMPONENT)) == "0.0.1"
    assert CENTRAL_COMPONENT not in {item.component_id for item in build_active_facade_bindings()}


def test_legacy_central_units_bridge_to_canonical_class_identity() -> None:
    from cogcoder.organization.central import CentralControlPlane as LegacyControl, CentralDirectWorkReceipt as LegacyWork
    from cogcoder.organization.central_access import CentralCoreAccessPolicy as LegacyAccess, CoreLease as LegacyCoreLease
    from cogcoder.organization.central_conflicts import (
        CentralConflictPacket as LegacyPacket,
        CentralConflictRegistry as LegacyConflictRegistry,
        ConflictClaim as LegacyClaim,
        ConflictStatus as LegacyConflictStatus,
    )
    from cogcoder.organization.central_resources import (
        CentralResourceArbiter as LegacyResourceArbiter,
        ResourceAllocationReceipt as LegacyAllocation,
        ResourceReleaseReceipt as LegacyRelease,
    )
    from cogcoder.organization.central_state import (
        CentralCapabilityMap as LegacyCapabilityMap,
        CentralCapabilityObservation as LegacyObservation,
        CentralWorldState as LegacyWorldState,
    )
    from nolane.organization.central import CentralControlPlane, CentralDirectWorkReceipt
    from nolane.organization.central_access import CentralCoreAccessPolicy, CoreLease
    from nolane.organization.central_conflicts import CentralConflictPacket, CentralConflictRegistry, ConflictClaim, ConflictStatus
    from nolane.organization.central_resources import CentralResourceArbiter, ResourceAllocationReceipt, ResourceReleaseReceipt
    from nolane.organization.central_state import CentralCapabilityMap, CentralCapabilityObservation, CentralWorldState

    pairs = (
        (LegacyControl, CentralControlPlane),
        (LegacyWork, CentralDirectWorkReceipt),
        (LegacyAccess, CentralCoreAccessPolicy),
        (LegacyCoreLease, CoreLease),
        (LegacyPacket, CentralConflictPacket),
        (LegacyConflictRegistry, CentralConflictRegistry),
        (LegacyClaim, ConflictClaim),
        (LegacyConflictStatus, ConflictStatus),
        (LegacyResourceArbiter, CentralResourceArbiter),
        (LegacyAllocation, ResourceAllocationReceipt),
        (LegacyRelease, ResourceReleaseReceipt),
        (LegacyCapabilityMap, CentralCapabilityMap),
        (LegacyObservation, CentralCapabilityObservation),
        (LegacyWorldState, CentralWorldState),
    )
    for legacy, canonical in pairs:
        assert legacy is canonical
        assert canonical.__module__.startswith("nolane.organization.central")


def test_native_central_modules_do_not_import_historical_behavior_modules() -> None:
    import importlib

    for module_name in CANONICAL_MODULES:
        module = importlib.import_module(module_name)
        source = inspect.getsource(module)
        behavior_imports = [
            line for line in source.splitlines()
            if "import" in line and "cogcoder.organization." in line
        ]
        assert all("cogcoder.organization.types" in line for line in behavior_imports), (module_name, behavior_imports)


def test_central_resource_arbiter_preserves_accounting_and_round_trip() -> None:
    from nolane.organization.central_resources import CentralResourceArbiter

    arbiter = CentralResourceArbiter({"compute": 100, "tool_calls": 20})
    allocation = arbiter.allocate(
        beneficiary="coding.backend.01",
        resource="compute",
        amount=30,
        reason="bounded-test",
        evidence_refs=("evidence-alloc",),
    )
    assert allocation.before_available == 100
    assert allocation.after_available == 70
    assert arbiter.leased_to("coding.backend.01", "compute") == 30
    release = arbiter.release(
        allocation.allocation_id,
        amount=10,
        reason="return-unused",
        evidence_refs=("evidence-release",),
    )
    assert release.after_leased == 20
    assert arbiter.available("compute") == 80
    restored = CentralResourceArbiter.from_state(arbiter.to_state())
    assert restored.to_state() == arbiter.to_state()


def test_central_conflict_registry_preserves_cross_region_evidence_and_round_trip() -> None:
    from nolane.organization.central_conflicts import CentralConflictRegistry, ConflictStatus

    registry = CentralConflictRegistry()
    packet = registry.open(
        submitted_by=("coding.chief", "debugging.chief"),
        regions=("core-coding", "debugging-failure-intelligence"),
        object_refs=("artifact-1",),
        claims=(
            ("coding.chief", "merge", ("evidence-coding",)),
            ("debugging.chief", "block", ("evidence-debug",)),
        ),
        severity=80,
    )
    assert packet.status is ConflictStatus.OPEN
    resolved = registry.resolve(
        packet.conflict_id,
        resolver_agent_id="nolane.central",
        decision="block pending verification",
        rationale="conflicting executable evidence",
        evidence_refs=("evidence-central",),
    )
    assert resolved.status is ConflictStatus.RESOLVED
    restored = CentralConflictRegistry.from_state(registry.to_state())
    assert restored.to_state() == registry.to_state()


def test_central_capability_map_preserves_evidence_and_round_trip() -> None:
    from nolane.organization.central_state import CentralCapabilityMap

    registry, _, _, _, _ = _substrate()
    mapping = CentralCapabilityMap(registry)
    row = mapping.observe(
        agent_id="coding.backend.01",
        readiness=77,
        health=91,
        evidence_refs=("eval-1",),
    )
    assert row.sequence == 1
    assert mapping.latest_for("coding.backend.01") == row
    restored = CentralCapabilityMap.from_state(registry, mapping.to_state())
    assert restored.to_state() == mapping.to_state()


def test_central_core_access_preserves_owner_budget_expiry_and_round_trip() -> None:
    from nolane.external_core.invokable import ExternalCoreRegistry, ExternalCoreSpec
    from nolane.organization.central_access import CentralCoreAccessPolicy

    registry, _, _, _, _ = _substrate()
    cores = ExternalCoreRegistry()
    cores.register(
        ExternalCoreSpec(
            core_id="private-coding-core",
            owner_agent_or_region="core-coding",
            capabilities=("compile",),
            input_schema="mapping",
            output_schema="mapping",
            side_effects=("filesystem",),
            required_permissions=("external_core.invoke",),
            cost_model="bounded",
            failure_modes=("unavailable",),
            verification_hooks=("receipt",),
            version="0.1",
        )
    )
    policy = CentralCoreAccessPolicy(registry, cores)
    assert not policy.can_invoke("private-coding-core", token=0)
    lease = policy.grant_lease(
        core_id="private-coding-core",
        owner="core-coding",
        call_budget=2,
        expires_at_token=5,
        reason="cross-region inspection",
        evidence_refs=("lease-evidence",),
    )
    assert policy.can_invoke("private-coding-core", token=5, lease_id=lease.lease_id)
    consumed = policy.consume(lease.lease_id, token=1)
    assert consumed.remaining_calls == 1
    restored = CentralCoreAccessPolicy.from_state(registry, cores, policy.to_state())
    assert restored.to_state() == policy.to_state()


def test_central_control_plane_preserves_evidence_directives_scheduler_and_round_trip() -> None:
    from nolane.external_core.invokable import ExternalCoreRegistry
    from nolane.organization.central import CentralControlPlane

    class VerificationStub:
        def to_state(self):
            return {"records": []}

    registry, ledger, authority, tasks, scheduler = _substrate()
    target = "coding.backend.01"
    scheduler.sleep(target)
    central = CentralControlPlane(
        registry=registry,
        ledger=ledger,
        authority=authority,
        tasks=tasks,
        scheduler=scheduler,
        artifacts=object(),
        external_cores=ExternalCoreRegistry(),
        self_models=object(),
        evolution=object(),
        verification=VerificationStub(),
    )

    question = central.question(target_agent_id=target, directive="show evidence")
    assert question.kind is EventKind.CENTRAL_QUESTION
    assert question.requires_ack
    assert target in scheduler.due_agents()

    with pytest.raises(ValueError):
        central.correct(target_agent_id=target, directive="fix", evidence_refs=())

    pause = central.pause(
        target_agent_id=target,
        directive="pause for verification",
        evidence_refs=("pause-evidence",),
    )
    assert pause.kind is EventKind.CENTRAL_PAUSE
    assert registry.get(target).status is AgentStatus.PAUSED

    state = central.to_state()
    restored = CentralControlPlane.from_state(
        registry=registry,
        ledger=ledger,
        authority=authority,
        tasks=tasks,
        scheduler=scheduler,
        artifacts=object(),
        external_cores=ExternalCoreRegistry(),
        self_models=object(),
        evolution=object(),
        verification=VerificationStub(),
        state=state,
    )
    assert restored.to_state() == state
