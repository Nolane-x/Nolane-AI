from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.skills import SkillEvolutionEngine, SkillRecord, SkillScope
