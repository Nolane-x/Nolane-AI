"""Canonical organization runtime namespace.

The accepted historical runtime is reachable only through the internal
Refoundation compatibility membrane. This public module exposes the canonical
organization boundary and does not re-export the raw legacy runtime class.
"""

from cogcoder.refoundation.canonical_runtime import CanonicalOrganization

COMPONENT_ID = "organization.runtime"
COMPONENT_VERSION = "0.0.0"
MIGRATED_FROM = "cogcoder.organization.runtime"

# Preserve the familiar type name without preserving legacy write authority.
OrganizationRuntime = CanonicalOrganization


def build_first_generation_runtime() -> CanonicalOrganization:
    return CanonicalOrganization.first_generation()


__all__ = (
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
    "CanonicalOrganization",
    "OrganizationRuntime",
    "build_first_generation_runtime",
)
