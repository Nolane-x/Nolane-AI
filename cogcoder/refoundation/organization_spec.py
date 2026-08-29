"""Compatibility bridge into the canonical AI-first organization specification."""

from nolane.ai.catalog import (
    CENTRAL_TOOLS,
    GENERAL_TOOLS,
    LOCAL_PARAMETER_BANDS,
    REGION_SPECS,
    SHARED_CORE_PARAMETERS,
    UNIVERSAL_COGNITIVE_CAPABILITIES,
    CanonicalRegionSpec,
    CanonicalRoleSpec,
    build_canonical_identity_states,
    load_profiles,
    load_regions,
    load_shared_external,
    load_shared_neural,
)

__all__ = (
    "CanonicalRoleSpec",
    "CanonicalRegionSpec",
    "UNIVERSAL_COGNITIVE_CAPABILITIES",
    "GENERAL_TOOLS",
    "CENTRAL_TOOLS",
    "SHARED_CORE_PARAMETERS",
    "LOCAL_PARAMETER_BANDS",
    "REGION_SPECS",
    "load_shared_neural",
    "load_shared_external",
    "load_regions",
    "load_profiles",
    "build_canonical_identity_states",
)
