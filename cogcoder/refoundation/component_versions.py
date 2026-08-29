"""Compatibility re-export of canonical component revision authority."""

from nolane.metadata import component_versions as _canonical
from nolane.metadata.component_versions import (
    component_revision_map,
    component_version,
    next_component_version,
)

_COMPONENT_REVISIONS = _canonical._COMPONENT_REVISIONS

__all__ = (
    "component_revision_map",
    "component_version",
    "next_component_version",
)
