"""Compatibility bridge for canonical task-lease coordination."""

from nolane.organization.coordination_leases import (
    LeaseCoordinator,
    LeaseStatus,
    StaleAgentReceipt,
    TaskLeaseReceipt,
)

MIGRATED_TO = "nolane.organization.coordination_leases"

__all__ = (
    "LeaseCoordinator",
    "LeaseStatus",
    "StaleAgentReceipt",
    "TaskLeaseReceipt",
    "MIGRATED_TO",
)
