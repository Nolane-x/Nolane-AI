"""Compatibility re-export of canonical facade metadata."""

from nolane.metadata.facades import (
    FacadeBinding,
    FacadeParityReport,
    build_active_facade_bindings,
    validate_active_facades,
)

__all__ = (
    "FacadeBinding",
    "FacadeParityReport",
    "build_active_facade_bindings",
    "validate_active_facades",
)
