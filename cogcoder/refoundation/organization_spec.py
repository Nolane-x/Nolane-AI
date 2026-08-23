"""Compatibility bridge into canonical AI-first organization authority.

Refoundation Wave 3 moves authoring authority to `shared/`, `regions/`,
`ai/`, and `nolane.ai`. Historical Refoundation consumers keep these names
without owning a second organization definition.
"""

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
)

__all__ = (
    "UNIVERSAL_COGNITIVE_CAPABILITIES",
    "GENERAL_TOOLS",
    "CENTRAL_TOOLS",
    "SHARED_CORE_PARAMETERS",
    "LOCAL_PARAMETER_BANDS",
    "CanonicalRoleSpec",
    "CanonicalRegionSpec",
    "REGION_SPECS",
    "build_canonical_identity_states",
)
