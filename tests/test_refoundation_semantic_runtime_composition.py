from __future__ import annotations

from pathlib import Path

from cogcoder.refoundation.manifests import build_component_manifests
from cogcoder.refoundation.runtime_composition import build_semantic_runtime_composition
from cogcoder.refoundation.runtime_state_map import build_runtime_state_bindings


def test_semantic_runtime_composition_owns_every_accepted_state_section_exactly_once() -> None:
    composition = build_semantic_runtime_composition()
    expected = {
        row.legacy_section: row.canonical_owner
        for row in build_runtime_state_bindings()
    }

    assert composition.section_owners == expected
    assert composition.owned_state_sections() == tuple(sorted(expected))
    assert composition.unowned_state_sections == ()
    assert composition.duplicate_state_sections == ()
    assert composition.lossless is True


def test_semantic_runtime_composition_uses_only_declared_component_graph_and_is_a_dag() -> None:
    composition = build_semantic_runtime_composition()
    declared = {row.component_id for row in build_component_manifests()}

    assert {row.component_id for row in composition.nodes} == declared
    assert composition.unresolved_dependencies() == ()
    assert set(composition.topological_order()) == declared
    assert len(composition.topological_order()) == len(declared)


def test_semantic_runtime_composition_has_no_historical_part_or_r_names() -> None:
    composition = build_semantic_runtime_composition()
    forbidden = ("runtime_part", "part-x", "part x", "r2.", "r2_")

    for row in composition.nodes:
        value = " ".join((row.component_id, row.domain, row.semantic_contract)).lower()
        assert not any(token in value for token in forbidden)


def test_canonical_namespaces_cross_accepted_runtime_through_one_bridge() -> None:
    root = Path(__file__).resolve().parents[1]
    bridge = root / "cogcoder" / "refoundation" / "accepted_runtime.py"
    legacy_import = "from cogcoder.organization.runtime import OrganizationRuntime"

    direct_importers: list[str] = []
    for package in (root / "cogcoder" / "refoundation", root / "nolane"):
        for path in package.rglob("*.py"):
            if legacy_import in path.read_text(encoding="utf-8"):
                direct_importers.append(path.relative_to(root).as_posix())

    assert direct_importers == [bridge.relative_to(root).as_posix()]

    canonical_text = (root / "cogcoder" / "refoundation" / "canonical_runtime.py").read_text(encoding="utf-8")
    identity_text = (root / "cogcoder" / "refoundation" / "identity_source.py").read_text(encoding="utf-8")
    assert "from .accepted_runtime import AcceptedOrganizationRuntime" in canonical_text
    assert "from .accepted_runtime import AcceptedOrganizationRuntime" in identity_text


def test_public_runtime_exports_semantic_composition_but_not_accepted_runtime() -> None:
    import nolane.runtime as runtime_api

    assert hasattr(runtime_api, "build_runtime_composition")
    assert hasattr(runtime_api, "SemanticRuntimeComposition")
    assert not hasattr(runtime_api, "OrganizationRuntime")
