"""Historical R2.2 Epistemic compatibility bridge.

Canonical implementation authority moved to ``nolane.external_core.epistemic``
in Refoundation Epoch 0 Wave 5L. ``EvidenceChunk`` remains available on this
historical surface for source compatibility, but is owned by Knowledge.
"""

from nolane.memory.knowledge import EvidenceChunk
from nolane.external_core.epistemic import Belief, ClaimRecord, EpistemicConflict, EpistemicWorkspace

__all__ = (
    "EvidenceChunk",
    "ClaimRecord",
    "Belief",
    "EpistemicConflict",
    "EpistemicWorkspace",
)
