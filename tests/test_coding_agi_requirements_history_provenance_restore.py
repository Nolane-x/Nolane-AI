from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.requirements import RequirementKind, RequirementNode


def _node(requirement_id: str, *, dependencies: tuple[str, ...] = ()) -> RequirementNode:
    return RequirementNode(
        requirement_id=requirement_id,
        title=f"Requirement {requirement_id}",
        kind=RequirementKind.FUNCTIONAL,
        description=f"Authoritative behavior for {requirement_id}.",
        dependencies=dependencies,
    )


def _runtime_state_with_two_revisions() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    runtime.requirements.apply_revision(
        actor_agent_id="requirements.chief",
        reason="establish first requirement",
        evidence_refs=("ev-req-1",),
        upserts=(_node("REQ-1"),),
    )
    runtime.requirements.apply_revision(
        actor_agent_id="requirements.chief",
        reason="establish dependent requirement",
        evidence_refs=("ev-req-2",),
        upserts=(_node("REQ-2", dependencies=("REQ-1",)),),
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.requirements.graph.version == 2
    assert restored.requirements.to_state() == state["requirements"]
    return state


def _runtime_state_with_proposal() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    runtime.requirements.apply_revision(
        actor_agent_id="requirements.chief",
        reason="establish requirement",
        evidence_refs=("ev-req-1",),
        upserts=(_node("REQ-1"),),
    )
    runtime.requirements.propose_change(
        source_agent_id="coding.backend.01",
        requirement_id="REQ-1",
        proposal="clarify accepted behavior",
        evidence_refs=("ev-proposal",),
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
        if event.get("target_agent_id") == "requirements.chief"
        and event.get("region") == "requirements-product"
        and _payload(event).get("requirements_action") == "changed"
    ]


def _proposal_event(state: dict[str, Any]) -> dict[str, Any]:
    matches = [
        event
        for event in state["ledger"]["events"]
        if event.get("target_agent_id") == "requirements.chief"
        and event.get("region") == "requirements-product"
        and _payload(event).get("requirements_action") == "change_proposed"
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
def test_restore_rejects_coercible_requirement_revision_version(value: object) -> None:
    state = _runtime_state_with_two_revisions()
    state["requirements"]["graph"]["revisions"][0]["version"] = value

    with pytest.raises(ValueError, match="requirement revision version"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("value", (True, "1", 1.0))
def test_restore_rejects_coercible_requirement_parent_version(value: object) -> None:
    state = _runtime_state_with_two_revisions()
    state["requirements"]["graph"]["revisions"][1]["parent_version"] = value

    with pytest.raises(ValueError, match="requirement parent version"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("revision_index", "parent_version"),
    (
        (0, 1),
        (1, None),
        (1, 2),
    ),
)
def test_restore_rejects_noncanonical_requirement_parent_chain(
    revision_index: int,
    parent_version: int | None,
) -> None:
    state = _runtime_state_with_two_revisions()
    state["requirements"]["graph"]["revisions"][revision_index]["parent_version"] = parent_version

    with pytest.raises(ValueError, match="requirement parent lineage"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_requirement_revision_without_matching_change_event() -> None:
    state = _runtime_state_with_two_revisions()
    assert len(_changed_events(state)) == 2
    state["ledger"]["events"].pop()

    with pytest.raises(ValueError, match="requirement change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_change_event_reclassified_with_valid_digest() -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    _rewrite_payload(event, requirements_action="change_proposed")

    with pytest.raises(ValueError, match="requirement change provenance"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("mutation", "value"),
    (
        ("version", 1),
        ("reason", "different persisted reason"),
    ),
)
def test_restore_rejects_change_event_with_wrong_payload_provenance(
    mutation: str,
    value: object,
) -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    _rewrite_payload(event, **{mutation: value})

    with pytest.raises(ValueError, match="requirement change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_change_event_with_nonexact_version_type() -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    _rewrite_payload(event, version=True)

    with pytest.raises(ValueError, match="requirement change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_change_event_with_wrong_actor_and_valid_digest() -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    event["source_agent_id"] = "coding.backend.01"
    _recompute_event_digest(event)

    with pytest.raises(ValueError, match="requirement change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_change_event_with_wrong_evidence_and_valid_digest() -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    event["evidence_refs"] = ["ev-other"]
    _recompute_event_digest(event)

    with pytest.raises(ValueError, match="requirement change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_change_event_with_wrong_changed_ids_and_valid_digest() -> None:
    state = _runtime_state_with_two_revisions()
    event = _changed_events(state)[-1]
    event["object_refs"] = ["REQ-1"]
    _recompute_event_digest(event)

    with pytest.raises(ValueError, match="requirement change provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_phantom_requirement_change_event() -> None:
    state = _runtime_state_with_proposal()
    event = _proposal_event(state)
    event["source_agent_id"] = "requirements.chief"
    event["object_refs"] = ["REQ-1"]
    event["evidence_refs"] = ["ev-phantom"]
    _rewrite_payload(
        event,
        requirements_action="changed",
        version=2,
        reason="phantom persisted revision",
    )

    with pytest.raises(ValueError, match="requirement change provenance"):
        OrganizationRuntime.from_state(state)
