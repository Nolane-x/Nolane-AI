from __future__ import annotations

from typing import Any

from nolane.memory import _learning_substrate_impl as _impl
from nolane.memory.experience import ExperienceLedger
from nolane.memory.fabric import MemoryFabric
from nolane.memory.learning_authority import LearningEvidenceAuthority
from nolane.memory.lifecycle import MemoryLifecycleLedger, MemoryRelationGraph
from nolane.memory.skills import SkillEvolutionEngine


MemoryKind = _impl.MemoryKind
EpistemicType = _impl.EpistemicType
LearningMemoryMetadata = _impl.LearningMemoryMetadata
MemoryTombstone = _impl.MemoryTombstone
RetrievedLearningMemory = _impl.RetrievedLearningMemory
LearningRetrievalBundle = _impl.LearningRetrievalBundle
SkillValidation = _impl.SkillValidation


class LearningSubstrate(_impl.LearningSubstrate):
    """Canonical governed boundary for External Core B learning orchestration."""

    def __init__(
        self,
        *,
        registry,
        events,
        memory: MemoryFabric | None = None,
        lifecycle: MemoryLifecycleLedger | None = None,
        relations: MemoryRelationGraph | None = None,
        skills: SkillEvolutionEngine | None = None,
        experiences: ExperienceLedger | None = None,
        learning_authority: LearningEvidenceAuthority | None = None,
    ) -> None:
        super().__init__(
            registry=registry,
            events=events,
            memory=memory,
            lifecycle=lifecycle,
            relations=relations,
            skills=skills,
            experiences=experiences,
            learning_authority=learning_authority,
        )
        # A LearningSubstrate is the policy owner for persistent skill promotion.
        # The shared engine remains locally compatible when used without this
        # substrate, but cannot bypass regression/causal governance once bound.
        self.skills._bind_governed_skill_promoter(self)


def __getattr__(name: str) -> Any:
    # Preserve direct imports of implementation-level compatibility symbols
    # while keeping exactly one public LearningSubstrate class identity.
    return getattr(_impl, name)


__all__ = (
    "MemoryKind",
    "EpistemicType",
    "LearningMemoryMetadata",
    "MemoryTombstone",
    "RetrievedLearningMemory",
    "LearningRetrievalBundle",
    "SkillValidation",
    "LearningSubstrate",
)
