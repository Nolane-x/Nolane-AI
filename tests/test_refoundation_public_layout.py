from __future__ import annotations

from nolane.organization.composition import build_component_graph, build_composition_lock
from nolane.organization.manifests import build_agent_identities, build_agent_manifests
from nolane.organization.regions import build_region_manifests
from nolane.runtime import build_runtime
from nolane.runtime.state import RuntimeStateMapper
from nolane.runtime.versioning import component_revision_map


def test_public_canonical_layout_exposes_67_agents_15_regions_and_component_graph() -> None:
    assert len(build_agent_manifests()) == 67
    assert len(build_agent_identities()) == 67
    assert len(build_region_manifests()) == 15
    components = build_component_graph()
    assert len(components) >= 50
    assert set(component_revision_map()) == {row.component_id for row in components}
    assert build_composition_lock().unresolved_dependencies() == ()


def test_public_runtime_and_state_migration_api_are_composable() -> None:
    runtime = build_runtime()
    state = runtime.to_state()
    bundle = RuntimeStateMapper().bundle_state(state)
    assert bundle.lossless
    assert bundle.restore_legacy_state() == state
    assert runtime.identity_source == "canonical-manifests"
