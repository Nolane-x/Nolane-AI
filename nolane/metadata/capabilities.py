from __future__ import annotations

from dataclasses import dataclass

from .manifests import build_bootstrap_agent_manifests
from .organization_spec import CENTRAL_TOOLS, GENERAL_TOOLS, REGION_SPECS


@dataclass(frozen=True, slots=True)
class ToolManifest:
    tool_id: str
    availability: str
    component_version: str = "0.0.0"

    def __post_init__(self) -> None:
        if not self.tool_id.strip():
            raise ValueError("tool id must be explicit")
        if self.availability not in {"general", "central"}:
            raise ValueError("tool availability must be general or central")


@dataclass(frozen=True, slots=True)
class ExternalCoreManifest:
    core_id: str
    scope: str
    owner_region: str
    component_version: str = "0.0.0"

    def __post_init__(self) -> None:
        if not self.core_id.strip() or not self.owner_region.strip():
            raise ValueError("external core id and owner region must be explicit")
        if self.scope not in {"central", "regional"}:
            raise ValueError("external core scope must be central or regional")


@dataclass(frozen=True, slots=True)
class AgentCapabilityProjection:
    agent_id: str
    tools: tuple[str, ...]
    external_cores: tuple[str, ...]


_CENTRAL_EXTERNAL_CORES: tuple[str, ...] = (
    "global-project-graph",
    "resource-arbiter",
    "direct-intervention-channel",
)


def build_tool_catalog() -> tuple[ToolManifest, ...]:
    rows = [ToolManifest(tool_id=tool_id, availability="general") for tool_id in GENERAL_TOOLS]
    rows.extend(
        ToolManifest(tool_id=tool_id, availability="central")
        for tool_id in CENTRAL_TOOLS[len(GENERAL_TOOLS):]
    )
    result = tuple(rows)
    if len(result) != 22 or len({row.tool_id for row in result}) != 22:
        raise ValueError("canonical base tool catalog must contain exactly 22 unique tool ids")
    return result


def build_external_core_catalog() -> tuple[ExternalCoreManifest, ...]:
    rows: list[ExternalCoreManifest] = [
        ExternalCoreManifest(core_id=core_id, scope="central", owner_region="global-command")
        for core_id in _CENTRAL_EXTERNAL_CORES
    ]
    for region in REGION_SPECS:
        rows.extend(
            ExternalCoreManifest(core_id=core_id, scope="regional", owner_region=region.region_id)
            for core_id in region.external_cores
        )
    result = tuple(rows)
    composite_ids = {(row.scope, row.owner_region, row.core_id) for row in result}
    if len(result) != 75 or len(composite_ids) != 75:
        raise ValueError("canonical external-core catalog must contain 75 Central/regional bindings")
    return result


def agent_capability_projection(agent_id: str) -> AgentCapabilityProjection:
    manifests = {row.agent_id: row for row in build_bootstrap_agent_manifests()}
    try:
        manifest = manifests[str(agent_id)]
    except KeyError as exc:
        raise KeyError(f"unknown permanent agent capability projection: {agent_id}") from exc

    catalog = build_tool_catalog()
    general = {row.tool_id for row in catalog if row.availability == "general"}
    central = {row.tool_id for row in catalog if row.availability == "central"}
    permitted_tool_ids = general | (central if manifest.rank == "central" else set())
    tools = tuple(tool_id for tool_id in manifest.tool_permissions if tool_id in permitted_tool_ids)

    # External cores are authoritative from their dedicated identity field. The
    # legacy tool_permissions list is intentionally ignored for this surface.
    external_cores = tuple(manifest.external_core_bindings)
    return AgentCapabilityProjection(
        agent_id=manifest.agent_id,
        tools=tools,
        external_cores=external_cores,
    )
