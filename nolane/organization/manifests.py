from nolane.ai.catalog import (
    CENTRAL_TOOLS,
    GENERAL_TOOLS,
    REGION_SPECS,
    UNIVERSAL_COGNITIVE_CAPABILITIES,
)
from nolane.metadata.manifests import AgentManifest, build_bootstrap_agent_manifests
from nolane.schemas.identity import AgentIdentity

COMPONENT_ID = "organization.identity"
COMPONENT_VERSION = "0.0.0"


def build_agent_manifests() -> tuple[AgentManifest, ...]:
    return build_bootstrap_agent_manifests()


def build_agent_identities() -> tuple[AgentIdentity, ...]:
    rows = tuple(AgentIdentity.from_state(row.identity_state()) for row in build_bootstrap_agent_manifests())
    if len(rows) != 67 or len({row.agent_id for row in rows}) != 67:
        raise ValueError("canonical identity authority requires exactly 67 unique permanent identities")
    return rows


__all__ = (
    "AgentManifest",
    "CENTRAL_TOOLS",
    "GENERAL_TOOLS",
    "REGION_SPECS",
    "UNIVERSAL_COGNITIVE_CAPABILITIES",
    "build_agent_identities",
    "build_agent_manifests",
)
