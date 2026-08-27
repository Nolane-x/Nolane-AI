"""Deprecated historical External Core import path.

Authoritative implementation now lives in :mod:`nolane.external_core.invokable`.
"""

from nolane.external_core.invokable import (
    ExternalCoreRegistry,
    ExternalCoreSpec,
    build_default_external_core_registry,
)
from nolane.organization.identity import AgentRegistry

__all__ = [
    "ExternalCoreSpec",
    "ExternalCoreRegistry",
    "build_default_external_core_registry",
    "AgentRegistry",
]
