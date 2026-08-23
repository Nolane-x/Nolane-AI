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
    "SkillEvolutionEngine": ("nolane.memory.skills", "SkillEvolutionEngine"),
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
