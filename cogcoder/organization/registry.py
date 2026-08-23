"""Compatibility bridge for the canonical AgentRegistry implementation.

Implementation authority moved to ``nolane.organization.identity`` in
Refoundation Wave 2. This historical module remains import-compatible and does
not own an independent registry implementation.
"""

from nolane.organization.identity import AgentRegistry

MIGRATED_TO = "nolane.organization.identity"

__all__ = ("AgentRegistry", "MIGRATED_TO")
