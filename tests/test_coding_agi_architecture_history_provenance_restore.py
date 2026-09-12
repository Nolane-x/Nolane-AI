from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.architecture import ArchitectureComponent, ComponentKind


def _component(component_id: str) -> ArchitectureComponent:
    return ArchitectureComponent(
        component_id=component_id,
        title=f"Component {component_id}",
        kind=ComponentKind.MODULE,
        owner_region="core-coding",
        trust_zone="internal",
    )


def _runtime_state_with_two_revisions() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id="architecture.chief",
        reason="establish first component",
        evidence_refs=("ev-arch-1",),
        upsert_components=(_component("ARCH-A"),),
    )
    runtime.architecture.apply_revision(
        actor_agent_id="architecture.chief",
        reason="establish second component",
        evidence_refs=("ev-arch-2",),
        upsert_components=(_component("ARCH-B"),),
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.architecture.graph.version == 2
    assert restored.architecture.to_state() == state["architecture"]
    return state


def _runtime_state_with_concern() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id="architecture.chief",
        reason="establish component",
        evidence_refs=("ev-arch-1",),
        upsert_components=(_component("ARCH-A"),),
    )
    runtime.architecture.propose_concern(
        source_agent_id="coding.backend.01",
        component_refs=("ARCH-A",),
        observation="boundary needs review",
        alternatives=("keep", "split"),
        evidence_refs=("ev-concern",),
        severity=35,
    )
    state = runtime.to_state()
    OrganizationRuntime.from_state(deepcopy(state))
    return state


def _payload(event_state: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(event_state["payload_json"])
    assert isinstance(value, dict)
    return value


def _changed_events(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        event
        for event in state["ledger"]["events"]
        if event.get("target_agent_id") == "architecture.chief"
        and event.get("region") == "architecture-system"
        and _payload(event).get("architecture_action") == "changed"
    ]


def _concern_event(state: dict[str, Any]) -> dict[str, Any]:
    matches = [
        event
        for event in state["ledger"]["events"]
        if event.get("target_agent_id") == "architecture.chief"
        and event.get("region") == "architecture-system"
        and _payload(event).get("architecture_action") == "concern"
    ]
    assert len(matches) == 1
    return matches[0]


def _recompute_event_digest(event_state: dict[str, Any]) -> None:
    envelope = {
        "event_id": event_state["event_id"],
        "sequence": event_state["sequence"],
        "kind": event_state["kind"],
        "source_agent_id": event_state["source_agent_id"],
        "target_agent_id": event_state["target_agent_id"],
        "region": event_state["region"],
        "payload_json": event_state["payload_json"],
        "scope": event_state.get("scope", "organization"),
        "causal_parent_ids": list(event_state.get("causal_parent_ids", ())),
        "object_refs": list(event_state.get("object_refs", ())),
        "evidence_refs": list(event_state.get("evidence_refs", ())),
        "priority": event_state.get("priority", 0),
        "requires_ack": event_state.get("requires_ack", False),
        "status": event_state.get("status", "emitted"),
        "created_at_logical": event_state.get("created_at_logical", event_state["sequence"]),
    }
    event_state["digest"] = canonical_digest(envelope)


def _rewrite_payload(event_state: dict[str, Any], **changes: Any) -> None:
    payload = _payload(event_state)
    payload.update(changes)
    event_state["payload_json"] = canonical_json(payload)
    _recompute_event_digest(event_state)


@pytest.mark.parametrize("value", (True, "1", 1.0))
def test_restore_rejects_coercible_architecture_revision_version(value: object) -> None:
    state = _runtime_state_with_two_revisions()
    state["architecture"]["graph"]["revisions"][0]["version"] = value

    with pytest.raises(ValueError, match="architecture revision version"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("value", (True, "1", 1.0))
def test_restore_rejects_coercible_architecture_parent_version(value: object) -> None:
    state = _runtime_state_with_two_revisions()
    state["architecture"]["graph"]["revisions"][1]["parent_version"] = value

    with pytest.raises(ValueError, match="architecture parent version"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("revision_index", "parent_version"),
    (
        (0, 1),
        (1, None),
        (1, 2),
    ),
)
def test_restore_rejects_noncanonical_architecture_parent_chain(
    revision_index: int,
    parent_version: int | None,
) -> None:
    state = _runtime_state_with_two_revisions()
    state["architecture"]["graph"]["revisions"][revision_index]["parent_version"] = parent_version

    with pytest.raises(ValueError, match="architecture parent lineage"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_architecture_revision_without_matching_change_event() -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    state["ledger"]["events"].remove(event)

    with pytest.raises(ValueError, match="architecture change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_architecture_change_event_reclassified_with_valid_digest() -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    _rewrite_payload(event, architecture_action="concern")

    with pytest.raises(ValueError, match="architecture change provenance"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("mutation", "value"),
    (
        ("version", 1),
        ("reason", "different persisted reason"),
    ),
)
def test_restore_rejects_architecture_change_event_with_wrong_payload_provenance(
    mutation: str,
    value: object,
) -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    _rewrite_payload(event, **{mutation: value})

    with pytest.raises(ValueError, match="architecture change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_architecture_change_event_with_nonexact_version_type() -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    _rewrite_payload(event, version=True)

    with pytest.raises(ValueError, match="architecture change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_architecture_change_event_with_wrong_actor_and_valid_digest() -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    event["source_agent_id"] = "coding.backend.01"
    _recompute_event_digest(event)

    with pytest.raises(ValueError, match="architecture change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_architecture_change_event_with_wrong_evidence_and_valid_digest() -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    event["evidence_refs"] = ["ev-other"]
    _recompute_event_digest(event)

    with pytest.raises(ValueError, match="architecture change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_architecture_change_event_with_wrong_changed_refs_and_valid_digest() -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    event["object_refs"] = ["ARCH-A"]
    _recompute_event_digest(event)

    with pytest.raises(ValueError, match="architecture change provenance"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("target_agent_id", "requirements.chief"),
        ("region", "architecture-shadow"),
    ),
)
def test_restore_rejects_architecture_change_event_moved_out_of_canonical_scope(
    field: str,
    value: str,
) -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    event[field] = value
    _recompute_event_digest(event)

    with pytest.raises(ValueError, match="architecture change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_phantom_architecture_change_event() -> None:
    state = _runtime_state_with_concern()
    event = _concern_event(state)
    event["source_agent_id"] = "architecture.chief"
    event["object_refs"] = ["ARCH-A"]
    event["evidence_refs"] = ["ev-phantom"]
    _rewrite_payload(
        event,
        architecture_action="changed",
        version=2,
        reason="phantom persisted revision",
    )

    with pytest.raises(ValueError, match="architecture change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_duplicate_architecture_change_event_version() -> None:
    state = _runtime_state_with_concern()
    canonical = _changed_events(state)[0]
    duplicate = _concern_event(state)
    duplicate["source_agent_id"] = canonical["source_agent_id"]
    duplicate["object_refs"] = list(canonical["object_refs"])
    duplicate["evidence_refs"] = list(canonical["evidence_refs"])
    payload = _payload(canonical)
    _rewrite_payload(
        duplicate,
        architecture_action="changed",
        version=payload["version"],
        reason=payload["reason"],
    )

    with pytest.raises(ValueError, match="architecture change provenance"):
        OrganizationRuntime.from_state(state)
