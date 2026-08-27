from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)


_PUBLIC_SYMBOLS = (
    "ComponentKind",
    "ComponentStatus",
    "EdgeKind",
    "InterfaceClass",
    "InterfaceStability",
    "ArchitectureComponent",
    "InterfaceContract",
    "ArchitectureEdge",
    "ArchitectureRevision",
    "ArchitectureGraph",
    "ArchitectureControlPlane",
)


def test_wave5o_canonical_architecture_owns_complete_public_implementation() -> None:
    import nolane.external_core.architecture as canonical

    assert all(getattr(canonical, name).__module__ == "nolane.external_core.architecture" for name in _PUBLIC_SYMBOLS)
    assert canonical.COMPONENT_ID == "external.architecture"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.architecture"


def test_wave5o_historical_architecture_is_exact_public_object_bridge() -> None:
    import cogcoder.organization.architecture as legacy
    import nolane.external_core.architecture as canonical

    for name in _PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(canonical, name)


def test_wave5o_canonical_architecture_has_no_reverse_authority_import() -> None:
    import nolane.external_core.architecture as canonical

    source_path = Path(canonical.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    offenders: list[str] = []
    has_native_digest_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cogcoder.organization.architecture" or alias.name.startswith(
                    "cogcoder.organization.architecture."
                ):
                    offenders.append(f"import:{node.lineno}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "cogcoder.organization.architecture" or module.startswith(
                "cogcoder.organization.architecture."
            ):
                offenders.append(f"from:{node.lineno}:{module}")
            if module == "nolane.core.canonical_digest" and any(
                alias.name == "canonical_digest" for alias in node.names
            ):
                has_native_digest_import = True

    assert offenders == [], "canonical Architecture reverse-imports historical Architecture authority: " + "; ".join(offenders)
    assert has_native_digest_import, "canonical Architecture must use native canonical-digest authority"


def test_wave5o_dependency_cycle_rejection_remains_atomic() -> None:
    from nolane.external_core.architecture import (
        ArchitectureComponent,
        ArchitectureEdge,
        ArchitectureGraph,
        ComponentKind,
        EdgeKind,
    )

    graph = ArchitectureGraph()
    graph.apply(
        actor_agent_id="architecture.chief",
        reason="establish canonical architecture",
        evidence_refs=("ev-architecture-1",),
        upsert_components=(
            ArchitectureComponent("A", "A", ComponentKind.MODULE, "architecture-system", "internal"),
            ArchitectureComponent("B", "B", ComponentKind.MODULE, "architecture-system", "internal"),
        ),
        upsert_edges=(ArchitectureEdge("edge-a-b", "A", "B", EdgeKind.DEPENDS_ON),),
    )
    before = graph.to_state()

    with pytest.raises(ValueError, match="cycle"):
        graph.apply(
            actor_agent_id="architecture.chief",
            reason="invalid reverse dependency",
            evidence_refs=("ev-architecture-2",),
            upsert_edges=(ArchitectureEdge("edge-b-a", "B", "A", EdgeKind.DEPENDS_ON),),
        )

    assert graph.to_state() == before


def test_wave5o_architecture_snapshot_round_trip_preserves_state_and_digest() -> None:
    from nolane.external_core.architecture import (
        ArchitectureComponent,
        ArchitectureGraph,
        ComponentKind,
    )

    graph = ArchitectureGraph()
    graph.apply(
        actor_agent_id="architecture.chief",
        reason="record component",
        evidence_refs=("ev-architecture",),
        upsert_components=(
            ArchitectureComponent(
                "service.api",
                "Service API",
                ComponentKind.SERVICE,
                "architecture-system",
                "trusted",
                requirement_refs=("req-1",),
                plan_refs=("plan-1",),
            ),
        ),
    )
    restored = ArchitectureGraph.from_state(graph.to_state())

    assert restored.to_state() == graph.to_state()
    assert restored.digest == graph.digest
    assert restored.version == graph.version == 1


def test_wave5o_architecture_component_version_and_authority_cutover() -> None:
    implementation = build_component_implementation_ledger()
    row = implementation["external.architecture"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.external_core.architecture"
    assert row.legacy_sources == ("cogcoder/organization/architecture.py",)
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("external.architecture")) == "0.0.1"

    facade_ids = {binding.component_id for binding in build_active_facade_bindings()}
    assert "external.architecture" not in facade_ids


def test_wave5o_generated_native_debt_no_longer_contains_architecture() -> None:
    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    serialized = json.dumps(state, sort_keys=True)
    assert "external.architecture" not in serialized

    implementation = build_component_implementation_ledger()
    non_native = [row for row in implementation.values() if row.status is not ImplementationStatus.CANONICAL_NATIVE]
    # Wave 5O established a ceiling of 30. Later extraction waves are allowed
    # to reduce debt further; a historical contract must never force regression.
    assert len(non_native) <= 30
