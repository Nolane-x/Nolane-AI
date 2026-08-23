"""Compatibility bridge for canonical Organization authority primitives."""

from nolane.organization.authority import AuthorityBlock, AuthorityGraph, OverrideReceipt

MIGRATED_TO = "nolane.organization.authority"

__all__ = ("AuthorityBlock", "AuthorityGraph", "OverrideReceipt", "MIGRATED_TO")
