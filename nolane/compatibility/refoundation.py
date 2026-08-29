"""Narrow behavioral compatibility membrane for accepted Epoch-0 substrates.

These imports are deliberately isolated here.  Canonical modules must not
reach directly into historical behavioral namespaces.  This membrane preserves
accepted runtime/Foundry behavior without granting those historical modules
canonical write authority.
"""

from cogcoder.refoundation.canonical_runtime import CanonicalOrganization
from cogcoder.refoundation.temporary_work_units import TemporaryWorkUnitManifest
from cogcoder.refoundation.work_units import (
    TemporaryWorkUnitBudget,
    TemporaryWorkUnitRequest,
    TemporaryWorkUnitService,
)

COMPATIBILITY_ONLY = True
CANONICAL_WRITE_AUTHORITY = False
APPROVED_BEHAVIORAL_SOURCES = (
    "cogcoder.refoundation.canonical_runtime",
    "cogcoder.refoundation.temporary_work_units",
    "cogcoder.refoundation.work_units",
)

__all__ = (
    "APPROVED_BEHAVIORAL_SOURCES",
    "CANONICAL_WRITE_AUTHORITY",
    "COMPATIBILITY_ONLY",
    "CanonicalOrganization",
    "TemporaryWorkUnitBudget",
    "TemporaryWorkUnitManifest",
    "TemporaryWorkUnitRequest",
    "TemporaryWorkUnitService",
)
