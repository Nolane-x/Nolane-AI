from __future__ import annotations

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


def _runtime_state_with_architecture_identities() -> dict[str, Any]:
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id="architecture.chief",
        reason="establish architecture identity collision fixture",
        evidence_refs=("ev-arch-collision",),
        upsert_components=(
            ArchitectureComponent(
                component_id="ARCH-A",
                title="Architecture A",
                kind=ComponentKind.MODULE,
                owner_region="core-coding",
                trust_zone="internal",
            ),
            ArchitectureComponent(
                component_id="ARCH-B",
                title="Architecture B",
                kind=ComponentKind.MODULE,
                owner_region="core-coding",
                trust_zone="internal",
            ),
        ),
        upsert_interfaces=(
            InterfaceContract(
                interface_id="IFACE-A",
                producer_component_id="ARCH-A",
                interface_class=InterfaceClass.API,
                semantic_version="1.0.0",
                signature_digest="sig-a",
                stability=InterfaceStability.INTERNAL,
            ),
        ),
        upsert_edges=(
            ArchitectureEdge(
                edge_id="EDGE-A",
                source_component_id="ARCH-A",
                target_component_id="ARCH-B",
                kind=EdgeKind.DEPENDS_ON,
            ),
        ),
    )
    state = runtime.to_state()
    restored = OrganizationRuntime.from_state(deepcopy(state))
    assert restored.architecture.to_state() == state["architecture"]
    return state


def test_restore_rejects_duplicate_architecture_component_identity() -> None:
    state = _runtime_state_with_architecture_identities()
    components = state["architecture"]["graph"]["components"]
    components.append(deepcopy(components[0]))

    with pytest.raises(ValueError, match="duplicate architecture component"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_duplicate_architecture_interface_identity() -> None:
    state = _runtime_state_with_architecture_identities()
    interfaces = state["architecture"]["graph"]["interfaces"]
    interfaces.append(deepcopy(interfaces[0]))

    with pytest.raises(ValueError, match="duplicate architecture interface"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_duplicate_architecture_edge_identity() -> None:
    state = _runtime_state_with_architecture_identities()
    edges = state["architecture"]["graph"]["edges"]
    edges.append(deepcopy(edges[0]))

    with pytest.raises(ValueError, match="duplicate architecture edge"):
        OrganizationRuntime.from_state(state)
