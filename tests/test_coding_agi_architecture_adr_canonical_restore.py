from __future__ import annotations

# Permanent Neural R2.13 ADR canonical restore and supersession provenance authority gate.

from copy import deepcopy
from typing import Any

import pytest

from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import canonical_digest


def _canonical_runtime_state() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id="architecture.chief",
        reason="R2.13 ADR restore fixture",
        evidence_refs=("EV-ADR-ARCH",),
        upsert_components=(
            ArchitectureComponent(
                component_id="ADR-COMP",
                title="ADR component",
                kind=ComponentKind.MODULE,
                owner_region="core-coding",
                trust_zone="internal",
            ),
        ),
    )
    first = runtime.adr.propose(
        source_agent_id="coding.backend.01",
        title="Choose persistence boundary",
        context="Direct storage access couples modules",
        alternatives=("repository-interface", "direct-storage"),
        decision="repository-interface",
        rationale="keep storage behind a stable boundary",
        architecture_refs=("ADR-COMP",),
        evidence_refs=("EV-ADR-1",),
    )
    runtime.adr.accept(
        first.adr_id,
        actor_agent_id="architecture.chief",
        evidence_refs=("EV-ADR-2",),
    )
    second = runtime.adr.propose(
        source_agent_id="architecture.chief",
        title="Evolve persistence boundary",
        context="Need async durability",
        alternatives=("event-store", "repository-interface"),
        decision="event-store",
        rationale="support durable async flow",
        architecture_refs=("ADR-COMP",),
        evidence_refs=("EV-ADR-3",),
    )
    runtime.adr.accept(
        second.adr_id,
        actor_agent_id="architecture.chief",
        evidence_refs=("EV-ADR-4",),
        supersedes=first.adr_id,
    )
    runtime.adr.propose(
        source_agent_id="coding.backend.01",
        title="Future transport boundary",
        context="Transport may need isolation",
        alternatives=("message-bus", "direct-call"),
        decision="message-bus",
        rationale="preserve transport isolation",
        architecture_refs=("ADR-COMP",),
        evidence_refs=("EV-ADR-5",),
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.adr.to_state() == state["adr"]
    return state


def _records(state: dict[str, Any]) -> list[dict[str, Any]]:
    return state["adr"]["records"]


def _resign(row: dict[str, Any], semantic_overrides: dict[str, Any] | None = None) -> None:
    semantic = deepcopy(row)
    if semantic_overrides:
        semantic.update(semantic_overrides)
    semantic.pop("digest", None)
    row["digest"] = canonical_digest(semantic)


def test_canonical_adr_runtime_state_round_trips() -> None:
    state = _canonical_runtime_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.adr.to_state() == state["adr"]


@pytest.mark.parametrize("mutation", ("extra", "missing-records", "missing-counter-empty"))
def test_restore_rejects_noncanonical_adr_ledger_keys(mutation: str) -> None:
    if mutation == "missing-counter-empty":
        state = OrganizationRuntime.first_generation().to_state()
        del state["adr"]["counter"]
    else:
        state = _canonical_runtime_state()
        if mutation == "extra":
            state["adr"]["unexpected"] = "value"
        else:
            del state["adr"]["records"]

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    "mutation",
    (
        "extra",
        "missing-status-default",
        "missing-accepted-by-default",
        "missing-supersedes-default",
        "missing-superseded-by-default",
    ),
)
def test_restore_rejects_noncanonical_adr_record_keys(mutation: str) -> None:
    state = _canonical_runtime_state()
    row = _records(state)[2]
    if mutation == "extra":
        row["unexpected"] = "value"
    elif mutation == "missing-status-default":
        del row["status"]
    elif mutation == "missing-accepted-by-default":
        del row["accepted_by"]
    elif mutation == "missing-supersedes-default":
        del row["supersedes"]
    elif mutation == "missing-superseded-by-default":
        del row["superseded_by"]
    else:  # pragma: no cover - parametrization is closed above.
        raise AssertionError(mutation)

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("field", ("records",))
def test_restore_rejects_non_json_list_adr_ledger_collections(field: str) -> None:
    state = _canonical_runtime_state()
    state["adr"][field] = tuple(state["adr"][field])

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("field", ("alternatives", "architecture_refs", "evidence_refs"))
def test_restore_rejects_non_json_list_adr_record_collections(field: str) -> None:
    state = _canonical_runtime_state()
    row = _records(state)[2]
    row[field] = tuple(row[field])

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_noncanonical_adr_record_order() -> None:
    state = _canonical_runtime_state()
    state["adr"]["records"] = list(reversed(_records(state)))

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_duplicate_adr_identity_rows() -> None:
    state = _canonical_runtime_state()
    _records(state).append(deepcopy(_records(state)[2]))

    with pytest.raises(ValueError, match="duplicate ADR identity"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("counter", ("3", 4))
def test_restore_rejects_noncanonical_adr_counter(counter: object) -> None:
    state = _canonical_runtime_state()
    state["adr"]["counter"] = counter

    with pytest.raises(ValueError, match="canonical ADR counter"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_noncontiguous_adr_identity_sequence() -> None:
    state = _canonical_runtime_state()
    row = _records(state)[2]
    row["adr_id"] = "ADR-00000004"
    _resign(row)
    state["adr"]["counter"] = 4

    with pytest.raises(ValueError, match="canonical ADR identity sequence"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("field", "raw_value", "semantic_value"),
    (
        ("source_agent_id", 7, "7"),
        ("accepted_by", 7, "7"),
    ),
)
def test_restore_rejects_scalar_type_laundering(
    field: str,
    raw_value: object,
    semantic_value: object,
) -> None:
    state = _canonical_runtime_state()
    row = _records(state)[1]
    row[field] = raw_value
    _resign(row, {field: semantic_value})

    with pytest.raises(ValueError, match="exact"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("record_index", "field", "value"),
    (
        (2, "source_agent_id", "ghost.agent"),
        (1, "accepted_by", "ghost.agent"),
    ),
)
def test_restore_rejects_unknown_adr_agents(record_index: int, field: str, value: str) -> None:
    state = _canonical_runtime_state()
    row = _records(state)[record_index]
    row[field] = value
    _resign(row)

    with pytest.raises((KeyError, ValueError), match="unknown|agent"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_unknown_adr_architecture_reference() -> None:
    state = _canonical_runtime_state()
    row = _records(state)[2]
    row["architecture_refs"] = ["MISSING-COMPONENT"]
    _resign(row)

    with pytest.raises(ValueError, match="architecture"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    "mutation",
    (
        "empty-title",
        "one-alternative",
        "empty-evidence",
        "proposed-with-accepted-by",
        "accepted-without-accepted-by",
    ),
)
def test_restore_rejects_adr_states_live_api_cannot_emit(mutation: str) -> None:
    state = _canonical_runtime_state()
    if mutation in {"empty-title", "one-alternative", "empty-evidence", "proposed-with-accepted-by"}:
        row = _records(state)[2]
    else:
        row = _records(state)[1]

    if mutation == "empty-title":
        row["title"] = ""
    elif mutation == "one-alternative":
        row["alternatives"] = ["message-bus"]
    elif mutation == "empty-evidence":
        row["evidence_refs"] = []
    elif mutation == "proposed-with-accepted-by":
        row["accepted_by"] = "architecture.chief"
    elif mutation == "accepted-without-accepted-by":
        row["accepted_by"] = None
    else:  # pragma: no cover - parametrization is closed above.
        raise AssertionError(mutation)
    _resign(row)

    with pytest.raises(ValueError, match="ADR|canonical|proposed|accepted|evidence|alternative"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    "mutation",
    (
        "superseded-missing-forward-link",
        "accepted-missing-back-link",
        "forward-link-points-to-proposed",
        "back-link-points-to-proposed",
    ),
)
def test_restore_rejects_incoherent_adr_supersession_provenance(mutation: str) -> None:
    state = _canonical_runtime_state()
    old = _records(state)[0]
    replacement = _records(state)[1]
    proposed = _records(state)[2]

    if mutation == "superseded-missing-forward-link":
        old["superseded_by"] = None
        _resign(old)
    elif mutation == "accepted-missing-back-link":
        replacement["supersedes"] = None
        _resign(replacement)
    elif mutation == "forward-link-points-to-proposed":
        old["superseded_by"] = proposed["adr_id"]
        _resign(old)
    elif mutation == "back-link-points-to-proposed":
        replacement["supersedes"] = proposed["adr_id"]
        _resign(replacement)
    else:  # pragma: no cover - parametrization is closed above.
        raise AssertionError(mutation)

    with pytest.raises(ValueError, match="ADR supersession|supersed"):
        OrganizationRuntime.from_state(state)
