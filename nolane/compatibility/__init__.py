"""Explicit non-authoritative compatibility membranes for post-Epoch Nolane.

Canonical code may depend on these membranes only when an accepted historical
runtime substrate is intentionally preserved.  The membrane itself never owns
canonical writes.
"""

COMPATIBILITY_ONLY = True
CANONICAL_WRITE_AUTHORITY = False

__all__ = ("COMPATIBILITY_ONLY", "CANONICAL_WRITE_AUTHORITY")
