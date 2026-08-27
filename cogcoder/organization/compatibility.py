"""Compatibility import bridge for the canonical External Core surface.

Runtime ownership lives in :mod:`nolane.external_core.compatibility`.
This module remains only to preserve accepted historical import paths.
"""

from nolane.external_core.compatibility import (
    CompatibilityAssessment,
    CompatibilityClass,
    CompatibilityEngine,
)

__all__ = [
    "CompatibilityAssessment",
    "CompatibilityClass",
    "CompatibilityEngine",
]
