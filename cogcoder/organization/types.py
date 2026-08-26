from __future__ import annotations

# Historical mixed-schema surface.  Semantic ownership now lives in focused
# canonical modules; these imports intentionally preserve exact public object
# identity for accepted historical callers.
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json
from nolane.external_core.context import ContextCapsule
from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.fabric import MemoryEntry, MemoryScope, MemoryStatus
from nolane.memory.skills import SkillScope
from nolane.organization.events import CognitiveEvent, EventKind
from nolane.schemas.identity import (
    PHYSICAL_PARAMETER_CEILING,
    AgentIdentity,
    AgentRank,
    AgentStatus,
    ParameterAccounting,
)
