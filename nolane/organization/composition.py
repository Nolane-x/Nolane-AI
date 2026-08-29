from nolane.metadata.composition import CompositionLock, build_wave1_composition_lock
from nolane.metadata.manifests import ComponentManifest, build_component_manifests

COMPONENT_ID = "organization.runtime"
COMPONENT_VERSION = "0.0.0"


def build_component_graph() -> tuple[ComponentManifest, ...]:
    return build_component_manifests()


def build_composition_lock() -> CompositionLock:
    return build_wave1_composition_lock()


__all__ = (
    "ComponentManifest",
    "CompositionLock",
    "build_component_graph",
    "build_composition_lock",
)
