"""Deprecated historical Integration import path.

Authoritative implementation now lives in :mod:`nolane.external_core.integration`.
"""

from nolane.external_core.integration import (
    ChangeCandidate,
    ChangeCandidateStatus,
    IntegrationControlPlane,
    IntegrationGraph,
    IntegrationReceipt,
)

__all__ = [
    "ChangeCandidateStatus",
    "ChangeCandidate",
    "IntegrationReceipt",
    "IntegrationGraph",
    "IntegrationControlPlane",
]
