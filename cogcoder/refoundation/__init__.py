"""Nolane-AI Refoundation Epoch 0 compatibility-first foundation.

Epoch 0 establishes independent canonical identities, regions, component
versions, composition, migration and parity contracts while the accepted
organization and historical R/Part implementation remain executable. Behavior
moves behind the canonical contracts only after parity and state-migration
evidence exists.
"""

from .census import CensusCoverage, CensusKind, RepositoryCensus, SourceCensusRecord
from .compatibility import BootstrapParityReport, build_bootstrap_parity_report
from .composition import CompositionLock, build_wave1_composition_lock
from .manifests import (
    FIRST_GENERATION_SNAPSHOT,
    REFUNDATION_EPOCH,
    AgentManifest,
    ComponentManifest,
    build_bootstrap_agent_manifests,
    build_component_manifests,
)
from .migration import LegacyDisposition, LegacyPathRecord, ReviewDepth
from .regions import RegionManifest, build_region_manifests
from .versioning import ComponentVersion

__all__ = (
    "AgentManifest",
    "BootstrapParityReport",
    "CensusCoverage",
    "CensusKind",
    "ComponentManifest",
    "ComponentVersion",
    "CompositionLock",
    "FIRST_GENERATION_SNAPSHOT",
    "LegacyDisposition",
    "LegacyPathRecord",
    "REFUNDATION_EPOCH",
    "RegionManifest",
    "RepositoryCensus",
    "ReviewDepth",
    "SourceCensusRecord",
    "build_bootstrap_agent_manifests",
    "build_bootstrap_parity_report",
    "build_component_manifests",
    "build_region_manifests",
    "build_wave1_composition_lock",
)
