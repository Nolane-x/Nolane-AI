from __future__ import annotations

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding import CodingControlPlane, CodingReadinessReceipt
from nolane.external_core.coding_profiles import CodingAssignmentReceipt, CodingWorkRequest
from nolane.external_core.debug_evidence import (
    DebugEvidenceArtifact,
    DebugEvidenceKind,
    DebugEvidenceLedger,
    FailureCase,
    FailureClass,
    ReproductionReceipt,
)
from nolane.external_core.debug_hypotheses import (
    DebugHypothesis,
    DebugHypothesisLedger,
    HypothesisStatus,
)
from nolane.external_core.debug_profiles import (
    DebugAssignmentReceipt,
    DebugProfileRegistry,
    DebugWorkRequest,
)
from nolane.memory.skills import SkillEvolutionEngine, SkillRecord
from nolane.organization.events import EventKind
from nolane.organization.identity import AgentRegistry
from nolane.organization.tasks import TaskGraph

from ._debugging_native import *
from ._debugging_native import DebugControlPlane, DebugPatchHandoff, DebugResolutionReceipt

COMPONENT_ID = "external.debugging"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.debugging"

# The accepted implementation executes inside the canonical package. Preserve
# the public module identity expected by serialization, introspection and exact
# historical bridge contracts.
DebugPatchHandoff.__module__ = __name__
DebugResolutionReceipt.__module__ = __name__
DebugControlPlane.__module__ = __name__
