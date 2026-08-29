"""Compatibility re-export of canonical implementation-status authority."""

from nolane.metadata import implementation_status as _canonical
from nolane.metadata.implementation_status import (
    ComponentImplementationRecord,
    ImplementationStatus,
    build_component_implementation_ledger,
)

_NATIVE = _canonical._NATIVE
_HISTORICAL_ONLY = _canonical._HISTORICAL_ONLY
_FROZEN_ASSET = _canonical._FROZEN_ASSET
_LEGACY_SOURCE_HINTS = _canonical._LEGACY_SOURCE_HINTS

__all__ = (
    "ComponentImplementationRecord",
    "ImplementationStatus",
    "build_component_implementation_ledger",
)
