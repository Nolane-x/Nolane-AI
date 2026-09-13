from __future__ import annotations

# Permanent Neural R2.9 exact-string Architecture authority gate.

from copy import deepcopy
import json
from typing import Any

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.architecture import (
    ArchitectureComponent,
    ArchitectureEdge,
    ArchitectureGraph,
    ArchitectureRevision,
    ComponentKind,
    EdgeKind,
    InterfaceClass,
    InterfaceContract,
    InterfaceStability,
)


def _runtime_state_with_string_shaped_architecture_values() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id="architecture.chief",
        reason="True",
        evidence_refs=("7",),
        upsert_components=(
            ArchitectureComponent(
                component_id="123",
                title="True",
                kind=ComponentKind.MODULE,
                owner_region="7",
                trust_zone="1.0",
                requirement_refs=("7",),
                plan_refs=("True",),
            ),
            ArchitectureComponent(
                component_id="456",
                title="Architecture B",
                kind=ComponentKind.MODULE,
                owner_region="core-coding",
                trust_zone="internal",
            ),
        ),
        upsert_interfaces=(
            InterfaceContract(
                interface_id="1.0",
                producer_component_id="123",
                interface_class=InterfaceClass.API,
                semantic_version="7",
                signature_digest="True",
                stability=InterfaceStability.INTERNAL,
                consumer_scope=("123",),
                compatibility_policy="7",
                trust_classification="True",
            ),
        ),
        upsert_edges=(
            ArchitectureEdge(
                edge_id="7",
                source_component_id="123",
                target_component_id="456",
                kind=EdgeKind.DEPENDS_ON,
            ),
        ),
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.architecture.to_state() == state["architecture"]
    return state


def _architecture_change_event(state: dict[str, Any]) -> dict[str, Any]:
    for event in reversed(state["ledger"]["events"]):
        payload = json.loads(event["payload_json"])
        if payload.get("architecture_action") == "changed":
            return event
    raise AssertionError("missing architecture change event fixture")


def _component(state: dict[str, Any], component_id: str) -> dict[str, Any]:
    return next(row for row in state["architecture"]["graph"]["components"] if row["component_id"] == component_id)


def test_live_component_rejects_non_string_identity() -> None:
    with pytest.raises(ValueError, match="exact non-empty string"):
        ArchitectureComponent(
            component_id=True,  # type: ignore[arg-type]
            title="component",
            kind=ComponentKind.MODULE,
            owner_region="core-coding",
            trust_zone="internal",
        )


def test_live_component_rejects_non_string_reference_item() -> None:
    with pytest.raises(ValueError, match="exact non-empty string"):
        ArchitectureComponent(
            component_id="component",
            title="component",
            kind=ComponentKind.MODULE,
            owner_region="core-coding",
            trust_zone="internal",
            requirement_refs=(7,),  # type: ignore[arg-type]
        )


def test_live_interface_rejects_non_string_consumer_scope_item() -> None:
    with pytest.raises(ValueError, match="exact non-empty string"):
        InterfaceContract(
            interface_id="interface",
            producer_component_id="component",
            interface_class=InterfaceClass.API,
            semantic_version="1.0.0",
            signature_digest="digest",
            stability=InterfaceStability.INTERNAL,
            consumer_scope=(123,),  # type: ignore[arg-type]
        )


def test_live_edge_rejects_non_string_identity() -> None:
    with pytest.raises(ValueError, match="exact non-empty string"):
        ArchitectureEdge(
            edge_id=7,  # type: ignore[arg-type]
            source_component_id="source",
            target_component_id="target",
            kind=EdgeKind.DEPENDS_ON,
        )


@pytest.mark.parametrize(
    ("kwargs", "match"),
    (
        ({"actor_agent_id": True, "reason": "reason", "evidence_refs": ("ev",)}, "actor"),
        ({"actor_agent_id": "actor", "reason": 7, "evidence_refs": ("ev",)}, "reason"),
        ({"actor_agent_id": "actor", "reason": "reason", "evidence_refs": (7,)}, "evidence"),
    ),
)
def test_live_graph_apply_rejects_non_string_revision_authority(kwargs: dict[str, Any], match: str) -> None:
    graph = ArchitectureGraph()
    component = ArchitectureComponent(
        component_id="component",
        title="component",
        kind=ComponentKind.MODULE,
        owner_region="core-coding",
        trust_zone="internal",
    )
    with pytest.raises(ValueError, match=match):
        graph.apply(upsert_components=(component,), **kwargs)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    (
        ("component_id", 123),
        ("title", True),
        ("owner_region", 7),
        ("trust_zone", 1.0),
    ),
)
def test_restore_rejects_component_scalar_string_coercion(field: str, invalid_value: object) -> None:
    state = _runtime_state_with_string_shaped_architecture_values()
    _component(state, "123")[field] = invalid_value

    with pytest.raises(ValueError, match="exact non-empty string"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_component_reference_string_coercion() -> None:
    state = _runtime_state_with_string_shaped_architecture_values()
    _component(state, "123")["requirement_refs"][0] = 7

    with pytest.raises(ValueError, match="exact non-empty string"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    (
        ("interface_id", 1.0),
        ("producer_component_id", 123),
        ("semantic_version", 7),
        ("signature_digest", True),
        ("compatibility_policy", 7),
        ("trust_classification", True),
    ),
)
def test_restore_rejects_interface_scalar_string_coercion(field: str, invalid_value: object) -> None:
    state = _runtime_state_with_string_shaped_architecture_values()
    state["architecture"]["graph"]["interfaces"][0][field] = invalid_value

    with pytest.raises(ValueError, match="exact non-empty string"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_interface_consumer_scope_string_coercion() -> None:
    state = _runtime_state_with_string_shaped_architecture_values()
    state["architecture"]["graph"]["interfaces"][0]["consumer_scope"][0] = 123

    with pytest.raises(ValueError, match="exact non-empty string"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    (
        ("edge_id", 7),
        ("source_component_id", 123),
    ),
)
def test_restore_rejects_edge_string_coercion(field: str, invalid_value: object) -> None:
    state = _runtime_state_with_string_shaped_architecture_values()
    state["architecture"]["graph"]["edges"][0][field] = invalid_value

    with pytest.raises(ValueError, match="exact non-empty string"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_revision_reason_string_coercion() -> None:
    state = _runtime_state_with_string_shaped_architecture_values()
    state["architecture"]["graph"]["revisions"][0]["reason"] = True

    with pytest.raises(ValueError, match="exact non-empty string"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_revision_evidence_string_coercion_even_when_event_coerces_identically() -> None:
    state = _runtime_state_with_string_shaped_architecture_values()
    state["architecture"]["graph"]["revisions"][0]["evidence_refs"][0] = 7
    _architecture_change_event(state)["evidence_refs"][0] = 7

    with pytest.raises(ValueError, match="exact non-empty string"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_revision_changed_ref_string_coercion_even_when_event_coerces_identically() -> None:
    state = _runtime_state_with_string_shaped_architecture_values()
    revision = state["architecture"]["graph"]["revisions"][0]
    event = _architecture_change_event(state)
    revision_index = revision["changed_refs"].index("123")
    event_index = event["object_refs"].index("123")
    revision["changed_refs"][revision_index] = 123
    event["object_refs"][event_index] = 123

    with pytest.raises(ValueError, match="exact non-empty string"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("field", ("actor_agent_id", "graph_digest"))
def test_revision_restore_rejects_non_string_authority_scalars(field: str) -> None:
    state: dict[str, Any] = {
        "version": 1,
        "parent_version": None,
        "actor_agent_id": "actor",
        "reason": "reason",
        "evidence_refs": ["ev"],
        "changed_refs": ["component"],
        "graph_digest": "digest",
    }
    state[field] = True

    with pytest.raises(ValueError, match="exact non-empty string"):
        ArchitectureRevision.from_state(state)
