from __future__ import annotations

import inspect
from pathlib import Path

from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT


def test_identity_authority_events_are_native_and_independently_versioned() -> None:
    ledger = build_component_implementation_ledger()
    expected = {
        "organization.identity": "nolane.organization.identity",
        "organization.authority": "nolane.organization.authority",
        "organization.events": "nolane.organization.events",
    }
    for component_id, module in expected.items():
        row = ledger[component_id]
        assert row.status is ImplementationStatus.CANONICAL_NATIVE
        assert row.canonical_module == module
        assert row.canonical_write_authority is True
        version = component_version(component_id)
        assert row.component_version == str(version)
        assert version.major == 0 and version.minor == 0
        # Wave 2 established the native revision floor; later waves may advance it locally.
        assert version.revision >= 1


def test_native_trio_is_not_registered_as_compatibility_facades() -> None:
    facade_ids = {row.component_id for row in build_active_facade_bindings()}
    assert {
        "organization.identity",
        "organization.authority",
        "organization.events",
    }.isdisjoint(facade_ids)


def test_native_trio_keeps_exact_legacy_to_canonical_migration_destinations() -> None:
    census = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT).to_census()
    assert census.get("cogcoder/organization/registry.py").canonical_destination == "nolane/organization/identity.py"
    assert census.get("cogcoder/organization/authority.py").canonical_destination == "nolane/organization/authority.py"
    assert census.get("cogcoder/organization/events.py").canonical_destination == "nolane/organization/events.py"


def test_legacy_modules_bridge_to_canonical_class_authority() -> None:
    from cogcoder.organization.authority import (
        AuthorityBlock as LegacyAuthorityBlock,
        AuthorityGraph as LegacyAuthorityGraph,
        OverrideReceipt as LegacyOverrideReceipt,
    )
    from cogcoder.organization.events import EventLedger as LegacyEventLedger
    from cogcoder.organization.registry import AgentRegistry as LegacyAgentRegistry
    from nolane.organization.authority import AuthorityBlock, AuthorityGraph, OverrideReceipt
    from nolane.organization.events import EventLedger
    from nolane.organization.identity import AgentRegistry

    assert LegacyAgentRegistry is AgentRegistry
    assert LegacyAuthorityBlock is AuthorityBlock
    assert LegacyAuthorityGraph is AuthorityGraph
    assert LegacyOverrideReceipt is OverrideReceipt
    assert LegacyEventLedger is EventLedger
    assert AgentRegistry.__module__ == "nolane.organization.identity"
    assert AuthorityGraph.__module__ == "nolane.organization.authority"
    assert EventLedger.__module__ == "nolane.organization.events"


def test_native_modules_do_not_import_their_legacy_implementations() -> None:
    import nolane.organization.authority as authority
    import nolane.organization.events as events
    import nolane.organization.identity as identity

    assert "cogcoder.organization.registry import" not in inspect.getsource(identity)
    assert "cogcoder.organization.authority import" not in inspect.getsource(authority)
    assert "cogcoder.organization.events import" not in inspect.getsource(events)


def test_native_registry_preserves_mutation_and_round_trip_contract() -> None:
    from nolane.organization.identity import AgentRegistry

    identities = build_first_generation_blueprint()
    registry = AgentRegistry(identities)
    before_ids = tuple(row.agent_id for row in registry.identities())
    target = registry.get("coding.backend.01")

    registry.bind_task(target.agent_id, "task-wave2")
    registry.set_checkpoint(target.agent_id, "checkpoint-wave2")
    registry.set_self_model_version(target.agent_id, "self-model-wave2")
    registry.accept_neural_version(target.agent_id, "NUC-wave2-candidate")

    restored = AgentRegistry.from_state(registry.to_state())
    assert tuple(row.agent_id for row in restored.identities()) == before_ids
    assert restored.get(target.agent_id).current_task == "task-wave2"
    assert restored.get(target.agent_id).checkpoint_id == "checkpoint-wave2"
    assert restored.get(target.agent_id).self_model_version == "self-model-wave2"
    assert restored.accepted_versions(target.agent_id)[-1] == "NUC-wave2-candidate"


def test_native_authority_preserves_fail_closed_write_contract_and_round_trip() -> None:
    from nolane.organization.authority import AuthorityGraph
    from nolane.organization.identity import AgentRegistry

    registry = AgentRegistry(build_first_generation_blueprint())
    graph = AuthorityGraph(registry)
    graph.claim_owner("artifact-wave2", "coding.chief")
    assert graph.can_write("coding.chief", "artifact-wave2")
    assert not graph.can_write("debug.chief", "artifact-wave2")

    block = graph.record_block("artifact-wave2", "verification.chief", reason="independent verification block")
    assert block.artifact_id == "artifact-wave2"
    assert not graph.can_write("coding.chief", "artifact-wave2")

    override = graph.central_override(
        artifact_id="artifact-wave2",
        reason="evidence-backed emergency intervention",
        evidence_ids=("evidence-wave2",),
    )
    assert graph.can_write("nolane.central", "artifact-wave2", override_id=override.override_id)

    restored = AuthorityGraph.from_state(registry, graph.to_state())
    assert restored.to_state() == graph.to_state()


def test_native_event_ledger_preserves_causal_digest_delivery_and_round_trip() -> None:
    from cogcoder.organization.types import EventKind
    from nolane.organization.events import EventLedger

    ledger = EventLedger()
    ledger.subscribe("coding.chief", EventKind.BUG_DISCOVERED, region="core-coding")
    first = ledger.append(
        EventKind.BUG_DISCOVERED,
        source_agent_id="debug.reproducer.01",
        region="core-coding",
        payload={"bug": "wave2"},
        evidence_refs=("evidence-wave2",),
    )
    second = ledger.append(
        EventKind.TASK_PROGRESS,
        source_agent_id="coding.chief",
        target_agent_id="nolane.central",
        causal_parent_ids=(first.event_id,),
        payload={"status": "triaged"},
    )

    assert ledger.deliverable_for("coding.chief") == (first,)
    assert ledger.deliverable_for("nolane.central") == (second,)
    assert len(first.digest) == 64 and len(second.digest) == 64

    restored = EventLedger.from_state(ledger.to_state())
    assert restored.to_state() == ledger.to_state()
    assert restored.get(second.event_id).causal_parent_ids == (first.event_id,)
