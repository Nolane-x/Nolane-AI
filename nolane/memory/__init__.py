"""Canonical memory/context/experience/skill boundaries.

The package exports stay source-compatible while loading lazily so historical
compatibility modules can bridge individual canonical subcomponents without
creating package-initialization cycles during the refoundation cutover.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    "ExperienceLedger": ("nolane.memory.experience", "ExperienceLedger"),
    "MemoryFabric": ("nolane.memory.fabric", "MemoryFabric"),
    "MemoryLifecycleLedger": ("nolane.memory.lifecycle", "MemoryLifecycleLedger"),
    "MemoryRelationGraph": ("nolane.memory.lifecycle", "MemoryRelationGraph"),
    "MemoryRetrievalBudget": ("nolane.memory.retrieval", "MemoryRetrievalBudget"),
    "MemoryRetrievalEngine": ("nolane.memory.retrieval", "MemoryRetrievalEngine"),
    "MemoryRetrievalPolicy": ("nolane.memory.adaptive_policy", "MemoryRetrievalPolicy"),
    "MemoryRetrievalReceipt": ("nolane.memory.adaptive_policy", "MemoryRetrievalReceipt"),
    "MemoryCompactionReceipt": ("nolane.memory.adaptive_policy", "MemoryCompactionReceipt"),
    "MemoryAnchorHealthReceipt": ("nolane.memory.adaptive_policy", "MemoryAnchorHealthReceipt"),
    "SkillEvolutionEngine": ("nolane.memory.skills", "SkillEvolutionEngine"),
    "LearningSubstrate": ("nolane.memory.public_learning_substrate", "LearningSubstrate"),
    "LearningMemoryMetadata": ("nolane.memory.learning_substrate", "LearningMemoryMetadata"),
    "MemoryKind": ("nolane.memory.learning_substrate", "MemoryKind"),
    "EpistemicType": ("nolane.memory.learning_substrate", "EpistemicType"),
}

__all__ = tuple(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, symbol = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), symbol)
    globals()[name] = value
    return value
