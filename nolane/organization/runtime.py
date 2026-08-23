from cogcoder.organization.runtime import *
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.refoundation.identity_source import build_manifest_driven_runtime

COMPONENT_ID = "organization.runtime"
COMPONENT_VERSION = "0.0.0"
MIGRATED_FROM = "cogcoder.organization.runtime"


def build_first_generation_runtime() -> OrganizationRuntime:
    """Canonical public bootstrap for the fixed 67-identity organization.

    The class remains identity-compatible with the accepted legacy runtime,
    while permanent identity authority now comes from Refoundation manifests.
    """

    return build_manifest_driven_runtime()


__all__ = tuple(name for name in globals() if not name.startswith("_"))
