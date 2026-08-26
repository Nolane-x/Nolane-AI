from __future__ import annotations

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.artifacts import ArtifactStore
from nolane.external_core.ui_coding import UICodingControlPlane
from nolane.external_core.ui_design import UXDesignLedger
from nolane.external_core.ui_observations import UIObservationLedger, Viewport
from nolane.external_core.ui_profiles import UIAssignmentReceipt, UIProfileRegistry, UIWorkRequest
from nolane.memory.skills import SkillEvolutionEngine, SkillRecord
from nolane.organization.events import EventKind

from ._ui_ux_native import *
from ._ui_ux_native import UIControlPlane, UIQualityEvidence, UIQualityKind, UIReadinessReceipt

COMPONENT_ID = "external.ui_ux"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.ui"

# The accepted implementation executes inside the canonical package. Preserve
# the public module identity expected by serialization, introspection and exact
# historical bridge contracts.
UIQualityKind.__module__ = __name__
UIQualityEvidence.__module__ = __name__
UIReadinessReceipt.__module__ = __name__
UIControlPlane.__module__ = __name__
