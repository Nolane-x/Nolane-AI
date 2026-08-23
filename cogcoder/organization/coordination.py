"""Compatibility bridge for canonical bounded coordination."""

from nolane.organization.coordination import (
    CoordinationBudget,
    CoordinationControlPlane,
    CoordinationEscalation,
    CoordinationMetrics,
    WakeDisposition,
    WakeReservation,
)

MIGRATED_TO = "nolane.organization.coordination"

__all__ = (
    "CoordinationBudget",
    "CoordinationControlPlane",
    "CoordinationEscalation",
    "CoordinationMetrics",
    "WakeDisposition",
    "WakeReservation",
    "MIGRATED_TO",
)
