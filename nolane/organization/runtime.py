from cogcoder.organization.runtime import *
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.refoundation.canonical_runtime import CanonicalOrganization

COMPONENT_ID = "organization.runtime"
COMPONENT_VERSION = "0.0.0"
MIGRATED_FROM = "cogcoder.organization.runtime"


def build_first_generation_runtime() -> CanonicalOrganization:
    """Canonical public bootstrap for the fixed 67-identity organization.

    ``OrganizationRuntime`` remains the accepted compatibility class, while
    this factory returns the Refoundation authority boundary: manifest-owned
    identities, MasterPlanGraph plan authority and LeaseCoordinator lease
    authority over the accepted execution implementation.
    """

    return CanonicalOrganization.first_generation()


__all__ = tuple(name for name in globals() if not name.startswith("_"))
