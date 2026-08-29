"""Canonical organization runtime namespace.

The public organization surface depends on the canonical runtime API rather
than reaching directly into Refoundation implementation modules.
"""

from nolane.runtime import CanonicalOrganization

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
