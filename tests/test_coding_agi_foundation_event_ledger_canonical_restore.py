from __future__ import annotations

# Permanent Neural R2.11 EventLedger restore gate; witnesses owner-file GREEN.

from copy import deepcopy
from typing import Any

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest
from nolane.organization.events import EventKind


def _canonical_runtime_state() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    runtime.ledger.subscribe("123", EventKind.BUG_DISCOVERED, region="456")
    first = runtime.ledger.append(
        EventKind.BUG_DISCOVERED,
        source_agent_id="123",
        payload={"value": "x"},
    )
    runtime.ledger.append(
        EventKind.TASK_PROGRESS,
        source_agent_id="source",
        target_agent_id="456",
        region="789",
        payload={"value": "y"},
        scope="303",
        causal_parent_ids=(first.event_id,),
        object_refs=("101",),
        evidence_refs=("202",),
        priority=7,
        requires_ack=True,
        status="404",
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.ledger.to_state() == state["ledger"]
    return state


def _ledger(state: dict[str, Any]) -> dict[str, Any]:
    return state["ledger"]


def _event(state: dict[str, Any], index: int) -> dict[str, Any]:
    return _ledger(state)["events"][index]


def _redigest(row: dict[str, Any]) -> None:
    row["digest"] = canonical_digest(
        {
            "event_id": row["event_id"],
            "sequence": row["sequence"],
            "kind": row["kind"],
            "source_agent_id": row["source_agent_id"],
            "target_agent_id": row["target_agent_id"],
            "region": row["region"],
            "payload_json": row["payload_json"],
            "scope": row["scope"],
            "causal_parent_ids": row["causal_parent_ids"],
            "object_refs": row["object_refs"],
            "evidence_refs": row["evidence_refs"],
            "priority": row["priority"],
            "requires_ack": row["requires_ack"],
            "status": row["status"],
            "created_at_logical": row["created_at_logical"],
        }
    )


def test_canonical_event_ledger_runtime_state_round_trips() -> None:
    state = _canonical_runtime_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.ledger.to_state() == state["ledger"]


@pytest.mark.parametrize("mutation", ("extra", "missing-events", "missing-subscriptions"))
def test_restore_rejects_noncanonical_event_ledger_record_keys(mutation: str) -> None:
    state = _canonical_runtime_state()
    ledger = _ledger(state)
    if mutation == "extra":
        ledger["unexpected"] = "value"
    elif mutation == "missing-events":
        del ledger["events"]
    elif mutation == "missing-subscriptions":
        del ledger["subscriptions"]
    else:  # pragma: no cover - parametrization is closed above.
        raise AssertionError(mutation)

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_non_json_list_event_collection() -> None:
    state = _canonical_runtime_state()
    ledger = _ledger(state)
    ledger["events"] = tuple(ledger["events"])

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    "mutation",
    (
        "extra",
        "missing-target",
        "missing-region",
        "missing-scope",
        "missing-causal-parents",
        "missing-object-refs",
        "missing-evidence-refs",
        "missing-priority",
        "missing-requires-ack",
        "missing-status",
        "missing-created-at",
    ),
)
def test_restore_rejects_noncanonical_event_record_keys(mutation: str) -> None:
    state = _canonical_runtime_state()
    row = _event(state, 0)
    if mutation == "extra":
        row["unexpected"] = "value"
    else:
        field = {
            "missing-target": "target_agent_id",
            "missing-region": "region",
            "missing-scope": "scope",
            "missing-causal-parents": "causal_parent_ids",
            "missing-object-refs": "object_refs",
            "missing-evidence-refs": "evidence_refs",
            "missing-priority": "priority",
            "missing-requires-ack": "requires_ack",
            "missing-status": "status",
            "missing-created-at": "created_at_logical",
        }[mutation]
        del row[field]

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("event_index", "field", "value"),
    (
        (0, "sequence", "1"),
        (0, "source_agent_id", 123),
        (1, "target_agent_id", 456),
        (1, "region", 789),
        (1, "scope", 303),
        (1, "priority", "7"),
        (1, "requires_ack", 1),
        (1, "status", 404),
        (1, "created_at_logical", "2"),
    ),
)
def test_restore_rejects_digest_preserving_scalar_coercion(
    event_index: int,
    field: str,
    value: object,
) -> None:
    state = _canonical_runtime_state()
    _event(state, event_index)[field] = value

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("causal_parent_ids", ("evt-00000001",)),
        ("object_refs", ("101",)),
        ("evidence_refs", ("202",)),
    ),
)
def test_restore_rejects_non_json_list_event_reference_collections(
    field: str,
    value: object,
) -> None:
    state = _canonical_runtime_state()
    _event(state, 1)[field] = value

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("object_refs", [101]),
        ("evidence_refs", [202]),
    ),
)
def test_restore_rejects_digest_preserving_reference_element_coercion(
    field: str,
    value: list[object],
) -> None:
    state = _canonical_runtime_state()
    _event(state, 1)[field] = value

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    "payload_json",
    (
        '{"value": "x"}',
        '{invalid',
    ),
)
def test_restore_rejects_noncanonical_event_payload_json(payload_json: str) -> None:
    state = _canonical_runtime_state()
    row = _event(state, 0)
    row["payload_json"] = payload_json
    _redigest(row)

    with pytest.raises(ValueError, match="event payload"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("parent_id", ("evt-00000001", "evt-00000002", "evt-99999999"))
def test_restore_rejects_causal_parent_not_strictly_before_child(parent_id: str) -> None:
    state = _canonical_runtime_state()
    row = _event(state, 0)
    row["causal_parent_ids"] = [parent_id]
    _redigest(row)

    with pytest.raises(ValueError, match="causal parent"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_created_at_logical_that_differs_from_sequence() -> None:
    state = _canonical_runtime_state()
    row = _event(state, 1)
    row["created_at_logical"] = 99
    _redigest(row)

    with pytest.raises(ValueError, match="created_at_logical"):
        OrganizationRuntime.from_state(state)


def _subscription_with_none_region(state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for agent_id, rows in _ledger(state)["subscriptions"].items():
        for row in rows:
            if row["region"] is None:
                return agent_id, row
    raise AssertionError("fixture must contain a subscription with region=None")


def test_restore_rejects_non_json_list_subscription_rows() -> None:
    state = _canonical_runtime_state()
    subscriptions = _ledger(state)["subscriptions"]
    agent_id = next(iter(subscriptions))
    subscriptions[agent_id] = tuple(subscriptions[agent_id])

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("mutation", ("extra", "missing-region"))
def test_restore_rejects_noncanonical_subscription_record_keys(mutation: str) -> None:
    state = _canonical_runtime_state()
    _, row = _subscription_with_none_region(state)
    if mutation == "extra":
        row["unexpected"] = "value"
    else:
        del row["region"]

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_digest_preserving_subscription_agent_id_coercion() -> None:
    state = _canonical_runtime_state()
    subscriptions = _ledger(state)["subscriptions"]
    subscriptions[123] = subscriptions.pop("123")

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_subscription_region_coercion() -> None:
    state = _canonical_runtime_state()
    row = _ledger(state)["subscriptions"]["123"][0]
    row["region"] = 456

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_duplicate_subscription_rows() -> None:
    state = _canonical_runtime_state()
    subscriptions = _ledger(state)["subscriptions"]
    agent_id = next(agent_id for agent_id, rows in subscriptions.items() if rows)
    subscriptions[agent_id].append(deepcopy(subscriptions[agent_id][0]))

    with pytest.raises(ValueError, match="duplicate subscription"):
        OrganizationRuntime.from_state(state)
