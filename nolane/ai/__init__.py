"""Canonical AI-first identity/core authority for Refoundation Epoch 0."""

from .catalog import (
    CENTRAL_TOOLS,
    GENERAL_TOOLS,
    LOCAL_PARAMETER_BANDS,
    REGION_SPECS,
    SHARED_CORE_PARAMETERS,
    UNIVERSAL_COGNITIVE_CAPABILITIES,
    build_canonical_identity_states,
    load_profiles,
    load_regions,
    load_shared_external,
    load_shared_neural,
)
from .resolver import render_resolved_markdown, resolve_ai, resolve_all

__all__ = (
    "CENTRAL_TOOLS",
    "GENERAL_TOOLS",
    "LOCAL_PARAMETER_BANDS",
    "REGION_SPECS",
    "SHARED_CORE_PARAMETERS",
    "UNIVERSAL_COGNITIVE_CAPABILITIES",
    "build_canonical_identity_states",
    "load_profiles",
    "load_regions",
    "load_shared_external",
    "load_shared_neural",
    "render_resolved_markdown",
    "resolve_ai",
    "resolve_all",
)
