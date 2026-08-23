from cogcoder.refoundation.identity_source import build_canonical_agent_identities
from cogcoder.refoundation.manifests import AgentManifest, build_bootstrap_agent_manifests
from cogcoder.refoundation.organization_spec import (
    CENTRAL_TOOLS,
    GENERAL_TOOLS,
    REGION_SPECS,
    UNIVERSAL_COGNITIVE_CAPABILITIES,
)

COMPONENT_ID = "organization.identity"
COMPONENT_VERSION = "0.0.0"


def build_agent_manifests() -> tuple[AgentManifest, ...]:
    return build_bootstrap_agent_manifests()


def build_agent_identities():
    return build_canonical_agent_identities()


__all__ = (
    "AgentManifest",
    "CENTRAL_TOOLS",
    "GENERAL_TOOLS",
    "REGION_SPECS",
    "UNIVERSAL_COGNITIVE_CAPABILITIES",
    "build_agent_identities",
    "build_agent_manifests",
)
