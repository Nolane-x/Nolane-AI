"""Compatibility bridge for canonical artifact-conflict coordination."""

from nolane.organization.coordination_conflicts import (
    ConflictClaim,
    ConflictCoordinator,
    ConflictPacket,
    ConflictResolutionReceipt,
    ConflictStatus,
)

MIGRATED_TO = "nolane.organization.coordination_conflicts"

__all__ = (
    "ConflictClaim",
    "ConflictCoordinator",
    "ConflictPacket",
    "ConflictResolutionReceipt",
    "ConflictStatus",
    "MIGRATED_TO",
)
