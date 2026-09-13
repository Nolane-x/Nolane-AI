from __future__ import annotations

# Permanent Neural R2.10 canonical serialized-state Architecture gate; this file also triggers the canonical suite.

from copy import deepcopy
from typing import Any

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.architecture import (
    ArchitectureComponent,
    ArchitectureEdge,
    ComponentKind,
    EdgeKind,
    InterfaceClass,
    InterfaceContract,
    InterfaceStability,
)


def _canonical_runtime_state() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id="architecture.chief",
        reason="canonical serialized-state fixture",
        evidence_refs=("evidence-b", "evidence-a"),
        upsert_components=(
            ArchitectureComponent(
                component_id="COMP-B",
                title="Component B",
                kind=ComponentKind.MODULE,
                owner_region="core-coding",
                trust_zone="internal",
                requirement_refs=("REQ-B",),
                plan_refs=("PLAN-B",),
            ),
            ArchitectureComponent(
                component_id="COMP-A",
                title="Component A",
                kind=ComponentKind.MODULE,
                owner_region="core-coding",
                trust_zone="internal",
                requirement_refs=("REQ-A",),
                plan_refs=("PLAN-A",),
            ),
        ),
        upsert_interfaces=(
            InterfaceContract(
                interface_id="IFACE-B",
                producer_component_id="COMP-B",
                interface_class=InterfaceClass.API,
                semantic_version="1.0.0",
                signature_digest="digest-b",
                stability=InterfaceStability.INTERNAL,
                consumer_scope=("COMP-A",),
            ),
            InterfaceContract(
                interface_id="IFACE-A",
                producer_component_id="COMP-A",
                interface_class=InterfaceClass.API,
                semantic_version="1.0.0",
                signature_digest="digest-a",
                stability=InterfaceStability.INTERNAL,
                consumer_scope=("COMP-B",),
            ),
        ),
        upsert_edges=(
            ArchitectureEdge(
                edge_id="EDGE-B",
                source_component_id="COMP-B",
                target_component_id="COMP-A",
                kind=EdgeKind.CALLS,
            ),
            ArchitectureEdge(
                edge_id="EDGE-A",
                source_component_id="COMP-A",
                target_component_id="COMP-B",
                kind=EdgeKind.DEPENDS_ON,
            ),
        ),
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.architecture.to_state() == state["architecture"]
    return state


def _graph(state: dict[str, Any]) -> dict[str, Any]:
    return state["architecture"]["graph"]


def test_canonical_architecture_runtime_state_round_trips() -> None:
    state = _canonical_runtime_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.architecture.to_state() == state["architecture"]


@pytest.mark.parametrize("field", ("components", "interfaces", "edges", "revisions"))
def test_restore_rejects_non_json_list_graph_collections(field: str) -> None:
    state = _canonical_runtime_state()
    graph = _graph(state)
    graph[field] = tuple(graph[field])

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    ("record", "field"),
    (
        ("component", "requirement_refs"),
        ("component", "plan_refs"),
        ("interface", "consumer_scope"),
        ("revision", "evidence_refs"),
        ("revision", "changed_refs"),
    ),
)
def test_restore_rejects_non_json_list_nested_sequences(record: str, field: str) -> None:
    state = _canonical_runtime_state()
    graph = _graph(state)
    if record == "component":
        row = graph["components"][0]
    elif record == "interface":
        row = graph["interfaces"][0]
    else:
        row = graph["revisions"][0]
    row[field] = tuple(row[field])

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize(
    "mutation",
    (
        "control-extra",
        "graph-extra",
        "component-extra",
        "component-missing-default",
        "interface-extra",
        "interface-missing-default",
        "edge-extra",
        "revision-extra",
        "revision-missing-parent",
    ),
)
def test_restore_rejects_noncanonical_serialized_record_keys(mutation: str) -> None:
    state = _canonical_runtime_state()
    graph = _graph(state)
    if mutation == "control-extra":
        state["architecture"]["unexpected"] = "value"
    elif mutation == "graph-extra":
        graph["unexpected"] = "value"
    elif mutation == "component-extra":
        graph["components"][0]["unexpected"] = "value"
    elif mutation == "component-missing-default":
        del graph["components"][0]["status"]
    elif mutation == "interface-extra":
        graph["interfaces"][0]["unexpected"] = "value"
    elif mutation == "interface-missing-default":
        del graph["interfaces"][0]["compatibility_policy"]
    elif mutation == "edge-extra":
        graph["edges"][0]["unexpected"] = "value"
    elif mutation == "revision-extra":
        graph["revisions"][0]["unexpected"] = "value"
    elif mutation == "revision-missing-parent":
        del graph["revisions"][0]["parent_version"]
    else:  # pragma: no cover - parametrization is closed above.
        raise AssertionError(mutation)

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)


@pytest.mark.parametrize("field", ("components", "interfaces", "edges"))
def test_restore_rejects_noncanonical_graph_identity_order(field: str) -> None:
    state = _canonical_runtime_state()
    graph = _graph(state)
    graph[field] = list(reversed(graph[field]))

    with pytest.raises(ValueError, match="canonical serialized state"):
        OrganizationRuntime.from_state(state)
