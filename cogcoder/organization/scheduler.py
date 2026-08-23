"""Compatibility bridge for canonical wake/sleep lifecycle scheduling."""

from nolane.organization.lifecycle import WakeSleepScheduler

MIGRATED_TO = "nolane.organization.lifecycle"

__all__ = ("WakeSleepScheduler", "MIGRATED_TO")
