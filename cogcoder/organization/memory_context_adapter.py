from __future__ import annotations

from dataclasses import replace
from typing import Any


class MemoryAwareContextCompiler:
    """Add Memory/Context private control-plane state without changing base context semantics."""

    def __init__(self, *, base_context: Any, memory_context: Any, registry: Any) -> None:
        self.base_context = base_context
        self.memory_context = memory_context
        self.registry = registry

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base_context, name)

    def compile(self, agent_id: str, *, task_id: str | None = None, since_event_id: str | None = None):
        capsule = self.base_context.compile(agent_id, task_id=task_id, since_event_id=since_event_id)
        identity = self.registry.get(agent_id)
        if identity.region != 'memory-context-knowledge':
            return capsule
        artifacts = tuple(capsule.authoritative_artifacts)
        if not any(name == 'memory-intelligence-state' for name, _ in artifacts):
            artifacts = artifacts + (('memory-intelligence-state', self.memory_context.digest),)
        return replace(capsule, authoritative_artifacts=artifacts)
