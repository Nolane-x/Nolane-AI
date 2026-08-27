"""Compatibility bridge for the canonical Requirements component.

Executable/write authority moved to :mod:`nolane.external_core.requirements`
in Refoundation Epoch 0 Wave 5M.  This historical import path remains stable
for provenance and downstream compatibility; it intentionally owns no second
Requirements implementation.
"""

from nolane.external_core.requirements import (
    AcceptanceCriterion,
    RequirementGraph,
    RequirementKind,
    RequirementNode,
    RequirementRevision,
    RequirementStatus,
    RequirementsControlPlane,
)


__all__ = [
    "AcceptanceCriterion",
    "RequirementGraph",
    "RequirementKind",
    "RequirementNode",
    "RequirementRevision",
    "RequirementStatus",
    "RequirementsControlPlane",
]
