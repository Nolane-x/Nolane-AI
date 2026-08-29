"""Compatibility re-export of canonical capability metadata."""

from nolane.metadata.capabilities import (
    AgentCapabilityProjection,
    ExternalCoreManifest,
    ToolManifest,
    agent_capability_projection,
    build_external_core_catalog,
    build_tool_catalog,
)

__all__ = (
    "AgentCapabilityProjection",
    "ExternalCoreManifest",
    "ToolManifest",
    "agent_capability_projection",
    "build_external_core_catalog",
    "build_tool_catalog",
)
