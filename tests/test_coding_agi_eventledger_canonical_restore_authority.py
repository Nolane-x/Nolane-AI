from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest
from nolane.organization.events import EventKind


_EVENT_ENVELOPE_FIELDS = (
    "event_id",
    "sequence",
    "kind",
    "source_agent_id",
    "target_agent_id",
    "region",
    "payload_json",
    "scope",
    "causal_parent_ids",
    "object_refs",
    "evidence_refs",
    "priority",
    "requires_ack",
    "status",
    "created_at_logical",
)


def _canonical_runtime_state() -> tuple[dict[str, Any], str, str]:
    runtime = OrganizationRuntime.first_generation()
    runtime.ledger.subscribe("123", EventKind.BUG_DISCOVERED, region="456")
    first = runtime.ledger.append(
        EventKind.BUG_DISCOVERED,
        source_agent_id="123",
        target_agent_id="789",
        region="456",
        payload={"b": 2, "a": 1},
        scope="101",
        object_refs=("202",),
        evidence_refs=("303",),
        priority=1,
        requires_ack=False,
        status="404",
    )
    second = runtime.ledger.append(
        EventKind.TASK_PROGRESS,
        source_agent_id="123",
        target_agent_id="789",
        region="456",
        payload={"status": "triaged"},
        scope="101",
        causal_parent_ids=(first.event_id,),
        object_refs=("202",),
        evidence_refs=("303",),
        priority=1,
        requires_ack=False,
        status="404",
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.ledger.to_state() == state["ledger"]
    return state, first.event_id, second.event_id


def _default_event_runtime_state() -> tuple[dict[str, Any], str]:
    runtime = OrganizationRuntime.first_generation()
    event = runtime.ledger.append(
        EventKind.TASK_PROGRESS,
        source_agent_id="coding.chief",
        payload={},
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.ledger.to_state() == state["ledger"]
    return state, event.event_id


def _event_row(state: dict[str, Any], event_id: str) -> dict[str, Any]:
    return next(row for row in state["ledger"]["events"] if row["event_id"] == event_id)


def _recompute_digest(row: dict[str, Any]) -> None:
    row["digest"] = canonical_digest({field: row[field] for field in _EVENT_ENVELOPE_FIELDS})


def test_canonical_eventledger_runtime_state_round_trips() -> None:
    state, _, _ = _canonical_runtime_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.ledger.to_state() == state["ledger"]


def test_restore_rejects_non_json_list_event_collection() -> None:
    state, _, _ = _canonical_runtime_state()
    state["ledger"]["events"] = tuple(state["ledger"]["events"])

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("field", ("causal_parent_ids", "object_refs", "evidence_refs"))
def test_restore_rejects_non_json_list_event_sequences(field: str) -> None:
    state, _, second_id = _canonical_runtime_state()
    row = _event_row(state, second_id)
    row[field] = tuple(row[field])

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_non_json_list_subscription_rows() -> None:
    state, _, _ = _canonical_runtime_state()
    state["ledger"]["subscriptions"]["123"] = tuple(
        state["ledger"]["subscriptions"]["123"]
    )

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    "mutation",
    (
        "ledger-extra",
        "event-extra",
        "subscription-extra",
        "ledger-missing-events",
        "ledger-missing-subscriptions",
        "subscription-missing-region",
    ),
)
def test_restore_rejects_noncanonical_serialized_record_keys(mutation: str) -> None:
    state, _, second_id = _canonical_runtime_state()
    if mutation == "ledger-extra":
        state["ledger"]["unexpected"] = "value"
    elif mutation == "event-extra":
        _event_row(state, second_id)["unexpected"] = "value"
    elif mutation == "subscription-extra":
        state["ledger"]["subscriptions"]["123"][0]["unexpected"] = "value"
    elif mutation == "ledger-missing-events":
        del state["ledger"]["events"]
    elif mutation == "ledger-missing-subscriptions":
        del state["ledger"]["subscriptions"]
    elif mutation == "subscription-missing-region":
        del state["ledger"]["subscriptions"]["123"][0]["region"]
    else:  # pragma: no cover - parametrization is closed above.
        raise AssertionError(mutation)

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    "field",
    (
        "target_agent_id",
        "region",
        "scope",
        "causal_parent_ids",
        "object_refs",
        "evidence_refs",
        "priority",
        "requires_ack",
        "status",
        "created_at_logical",
    ),
)
def test_restore_rejects_missing_event_fields_that_used_to_default(field: str) -> None:
    state, event_id = _default_event_runtime_state()
    del _event_row(state, event_id)[field]

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    "field",
    (
        "sequence",
        "source_agent_id",
        "target_agent_id",
        "region",
        "scope",
        "priority",
        "requires_ack",
        "status",
        "created_at_logical",
    ),
)
def test_restore_rejects_digest_preserving_scalar_type_laundering(field: str) -> None:
    state, _, second_id = _canonical_runtime_state()
    row = _event_row(state, second_id)
    replacements: dict[str, object] = {
        "sequence": str(row["sequence"]),
        "source_agent_id": 123,
        "target_agent_id": 789,
        "region": 456,
        "scope": 101,
        "priority": str(row["priority"]),
        "requires_ack": int(row["requires_ack"]),
        "status": 404,
        "created_at_logical": str(row["created_at_logical"]),
    }
    row[field] = replacements[field]

    with pytest.raises(ValueError, match="exact"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("field", ("object_refs", "evidence_refs"))
def test_restore_rejects_digest_preserving_reference_item_type_laundering(field: str) -> None:
    state, _, second_id = _canonical_runtime_state()
    row = _event_row(state, second_id)
    row[field][0] = 202 if field == "object_refs" else 303

    with pytest.raises(ValueError, match="exact"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_noncanonical_payload_json_even_with_matching_digest() -> None:
    state, first_id, _ = _canonical_runtime_state()
    row = _event_row(state, first_id)
    row["payload_json"] = '{"b": 2, "a": 1}'
    _recompute_digest(row)

    with pytest.raises(ValueError, match="canonical event payload"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_non_object_payload_json_even_with_matching_digest() -> None:
    state, first_id, _ = _canonical_runtime_state()
    row = _event_row(state, first_id)
    row["payload_json"] = "[]"
    _recompute_digest(row)

    with pytest.raises(ValueError, match="event payload"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_noncanonical_logical_time_even_with_matching_digest() -> None:
    state, _, second_id = _canonical_runtime_state()
    row = _event_row(state, second_id)
    row["created_at_logical"] = 999
    _recompute_digest(row)

    with pytest.raises(ValueError, match="logical time"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("causal_parent", ("evt-99999999", "future"))
def test_restore_rejects_causal_parent_without_prior_event_even_with_matching_digest(
    causal_parent: str,
) -> None:
    state, first_id, second_id = _canonical_runtime_state()
    row = _event_row(state, first_id if causal_parent == "future" else second_id)
    row["causal_parent_ids"] = [second_id if causal_parent == "future" else causal_parent]
    _recompute_digest(row)

    with pytest.raises(ValueError, match="causal parent"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_non_string_subscription_identity_without_normalizing_it() -> None:
    state, _, _ = _canonical_runtime_state()
    rows = state["ledger"]["subscriptions"].pop("123")
    state["ledger"]["subscriptions"][123] = rows

    with pytest.raises(ValueError, match="exact"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_non_string_subscription_region_without_normalizing_it() -> None:
    state, _, _ = _canonical_runtime_state()
    state["ledger"]["subscriptions"]["123"][0]["region"] = 456

    with pytest.raises(ValueError, match="exact"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_duplicate_subscription_rows_live_subscribe_cannot_emit() -> None:
    state, _, _ = _canonical_runtime_state()
    rows = state["ledger"]["subscriptions"]["123"]
    rows.append(deepcopy(rows[0]))

    with pytest.raises(ValueError, match="duplicate subscription"):
        OrganizationRuntime.from_state(state)
