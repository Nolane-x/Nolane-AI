"""Canonical Nolane runtime API.

This package is the clean Refoundation entrypoint. Historical
``cogcoder.organization.runtime*`` modules remain compatibility implementation
and evidence sources until their migration receipts permit archival.
"""

from cogcoder.refoundation.canonical_runtime import CanonicalOrganization

from .composition import (
    SemanticRuntimeComposition,
    SemanticRuntimeNode,
    build_runtime_composition,
)


def build_runtime() -> CanonicalOrganization:
    return CanonicalOrganization.first_generation()


__all__ = (
    "CanonicalOrganization",
    "SemanticRuntimeComposition",
    "SemanticRuntimeNode",
    "build_runtime",
    "build_runtime_composition",
)
