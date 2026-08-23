from __future__ import annotations

from cogcoder.refoundation.capabilities import (
    agent_capability_projection,
    build_external_core_catalog,
    build_tool_catalog,
)


def test_external_core_catalog_covers_exact_central_and_regional_bindings() -> None:
    cores = build_external_core_catalog()
    assert len(cores) == 75
    assert len({(row.scope, row.owner_region, row.core_id) for row in cores}) == 75
    assert sum(row.scope == "central" for row in cores) == 3
    assert sum(row.scope == "regional" for row in cores) == 72
    assert all(row.component_version == "0.0.0" for row in cores)


def test_tool_catalog_is_exact_22_base_tool_capabilities() -> None:
    tools = build_tool_catalog()
    assert len(tools) == 22
    assert len({row.tool_id for row in tools}) == 22
    assert sum(row.availability == "general" for row in tools) == 8
    assert sum(row.availability == "central" for row in tools) == 14
    assert all(row.component_version == "0.0.0" for row in tools)


def test_canonical_agent_projection_separates_tools_from_external_cores() -> None:
    central = agent_capability_projection("nolane.central")
    coding = agent_capability_projection("coding.backend.01")
    requirements = agent_capability_projection("requirements.analysis.01")

    assert len(central.tools) == 22
    assert len(central.external_cores) == 3
    assert len(coding.tools) == 8
    assert len(coding.external_cores) == 7
    assert len(requirements.tools) == 8
    assert len(requirements.external_cores) == 3
    assert "patch-engine" not in coding.tools
    assert "patch-engine" in coding.external_cores


def test_name_overlap_does_not_collapse_tool_and_external_core_types() -> None:
    central = agent_capability_projection("nolane.central")
    coding = agent_capability_projection("coding.backend.01")
    assert "lsp" in central.tools
    assert "lsp" in coding.external_cores
    assert "lsp" not in coding.tools
