"""Canonical Nolane runtime API.

Canonical authority lives in this namespace.  The accepted Epoch-0 behavioral
substrate is reachable only through ``nolane.compatibility`` and carries no
canonical write authority of its own.
"""

from nolane.compatibility.refoundation import CanonicalOrganization

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
