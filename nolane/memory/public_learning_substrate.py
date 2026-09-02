from __future__ import annotations

from nolane.memory.experience import ExperienceLedger
from nolane.memory.fabric import MemoryFabric
from nolane.memory.learning_authority import LearningEvidenceAuthority
from nolane.memory.learning_substrate import LearningSubstrate as _LearningSubstrate
from nolane.memory.lifecycle import MemoryLifecycleLedger, MemoryRelationGraph
from nolane.memory.skills import SkillEvolutionEngine


class LearningSubstrate(_LearningSubstrate):
    """Canonical public LearningSubstrate with its skill policy boundary bound."""

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
        # The canonical public substrate owns the promotion-policy boundary for
        # the exact shared skill engine. The engine keeps local standalone
        # compatibility when it is constructed outside this public substrate.
        self.skills._bind_governed_skill_promoter(self)


__all__ = ("LearningSubstrate",)
