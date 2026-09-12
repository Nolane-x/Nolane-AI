from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.planning import PlanNode


def _runtime_state_with_rollback() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    runtime.planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="first provenance witness",
        evidence_refs=("ev-plan-1",),
        upsert_nodes=(PlanNode("plan-a", "Plan A"),),
    )
    runtime.planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="second provenance witness",
        evidence_refs=("ev-plan-2",),
        upsert_nodes=(PlanNode("plan-b", "Plan B"),),
    )
    runtime.planning.rollback(
        actor_agent_id="planning.chief",
        source_revision=1,
        reason="restore first accepted plan",
        evidence_refs=("ev-rollback",),
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.planning.graph.version == 3
    assert restored.planning.revisions()[-1].source_revision == 1
    return state


def _runtime_state_without_rollback() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    runtime.planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="first ordinary revision",
        evidence_refs=("ev-plan-1",),
        upsert_nodes=(PlanNode("plan-a", "Plan A"),),
    )
    runtime.planning.apply_revision(
        actor_agent_id="planning.chief",
        reason="second ordinary revision",
        evidence_refs=("ev-plan-2",),
        upsert_nodes=(PlanNode("plan-b", "Plan B"),),
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.planning.graph.version == 2
    assert all(revision.source_revision is None for revision in restored.planning.revisions())
    return state


def _payload(event_state: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(event_state["payload_json"])
    assert isinstance(value, dict)
    return value


def _rollback_event(state: dict[str, Any]) -> dict[str, Any]:
    matches = [
        event
        for event in state["ledger"]["events"]
        if _payload(event).get("plan_action") == "rollback"
    ]
    assert len(matches) == 1
    return matches[0]


def _rewrite_payload(event_state: dict[str, Any], **changes: Any) -> None:
    payload = _payload(event_state)
    payload.update(changes)
    event_state["payload_json"] = canonical_json(payload)
    _recompute_event_digest(event_state)


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


def test_restore_rejects_event_with_noncanonical_digest() -> None:
    state = _runtime_state_with_rollback()
    _rollback_event(state)["digest"] = "0" * 64

    with pytest.raises(ValueError, match="event digest mismatch"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_rollback_revision_that_lost_its_source_marker() -> None:
    state = _runtime_state_with_rollback()
    state["planning"]["graph"]["revisions"][2]["source_revision"] = None

    with pytest.raises(ValueError, match="plan rollback provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_rollback_revision_without_matching_event() -> None:
    state = _runtime_state_with_rollback()
    state["ledger"]["events"].pop()

    with pytest.raises(ValueError, match="plan rollback provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_rollback_event_reclassified_as_revision_with_valid_digest() -> None:
    state = _runtime_state_with_rollback()
    event = _rollback_event(state)
    _rewrite_payload(event, plan_action="revision")

    with pytest.raises(ValueError, match="plan rollback provenance"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("old_version", 1),
        ("new_version", 2),
        ("source_revision", 2),
        ("source_revision", True),
    ),
)
def test_restore_rejects_rollback_event_with_wrong_version_provenance(
    field: str,
    value: object,
) -> None:
    state = _runtime_state_with_rollback()
    event = _rollback_event(state)
    _rewrite_payload(event, **{field: value})

    with pytest.raises(ValueError, match="plan rollback provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_rollback_event_with_wrong_actor_and_valid_digest() -> None:
    state = _runtime_state_with_rollback()
    event = _rollback_event(state)
    event["source_agent_id"] = "requirements.chief"
    _recompute_event_digest(event)

    with pytest.raises(ValueError, match="plan rollback provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_rollback_event_with_wrong_evidence_and_valid_digest() -> None:
    state = _runtime_state_with_rollback()
    event = _rollback_event(state)
    event["evidence_refs"] = ["ev-other"]
    _recompute_event_digest(event)

    with pytest.raises(ValueError, match="plan rollback provenance"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_phantom_rollback_event_for_ordinary_revision() -> None:
    state = _runtime_state_without_rollback()
    event = state["ledger"]["events"][-1]
    _rewrite_payload(event, plan_action="rollback", source_revision=1)

    with pytest.raises(ValueError, match="plan rollback provenance"):
        OrganizationRuntime.from_state(state)
