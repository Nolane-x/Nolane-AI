"""Compatibility re-export of canonical migration metadata."""

from nolane.metadata.migration import (
    LegacyDisposition,
    LegacyPathRecord,
    ReviewDepth,
    WAVE1_PRESERVED_LEGACY_PATHS,
)

__all__ = (
    "LegacyDisposition",
    "LegacyPathRecord",
    "ReviewDepth",
    "WAVE1_PRESERVED_LEGACY_PATHS",
)
