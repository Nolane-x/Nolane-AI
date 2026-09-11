from __future__ import annotations

from dataclasses import replace
from typing import Any

from nolane.core.canonical_digest import canonical_digest


class MemoryAwareContextCompiler:
    """Add Memory/Context private control-plane state without changing base context semantics."""

    def __init__(self, *, base_context: Any, memory_context: Any, registry: Any) -> None:
        self.base_context = base_context
        self.memory_context = memory_context
        self.registry = registry

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base_context, name)

    def _memory_authority_digest(self) -> str:
        """Digest semantic Memory/Context authority, excluding read/compile journals.

        Context compilation records retrieval selections, semantic deltas, and receipts.
        Those records are evidence *of* reading authority, not authority mutations. Binding
        them into the request authority would make every context compilation invalidate
        its own request as soon as its receipt is persisted.
        """

        state = self.memory_context.to_state()
        intelligence = dict(state.get('context_intelligence', {}))
        authority_state = {
            'profiles': state.get('profiles', {}),
            'lifecycle': state.get('lifecycle', {}),
            'relations': state.get('relations', {}),
            'context_intelligence': {
                'compiler_version': intelligence.get('compiler_version'),
                'checkpoints': intelligence.get('checkpoints', []),
                'checkpoint_counter': int(intelligence.get('checkpoint_counter', 0)),
            },
            'repairs': state.get('repairs', []),
            'repair_counter': int(state.get('repair_counter', 0)),
        }
        return canonical_digest(authority_state)

    def _with_memory_authority(
        self,
        agent_id: str,
        artifacts: tuple[tuple[str, Any], ...],
    ) -> tuple[tuple[str, Any], ...]:
        identity = self.registry.get(agent_id)
        if (
            identity.region == 'memory-context-knowledge'
            and not any(name == 'memory-intelligence-state' for name, _ in artifacts)
        ):
            return artifacts + (
                ('memory-intelligence-state', self._memory_authority_digest()),
            )
        return artifacts

    def authoritative_artifacts(
        self,
        agent_id: str,
        *,
        task_id: str | None = None,
    ) -> tuple[tuple[str, Any], ...]:
        artifacts = tuple(
            self.base_context.authoritative_artifacts(agent_id, task_id=task_id)
        )
        return self._with_memory_authority(agent_id, artifacts)

    def compile(self, agent_id: str, *, task_id: str | None = None, since_event_id: str | None = None):
        capsule = self.base_context.compile(agent_id, task_id=task_id, since_event_id=since_event_id)
        artifacts = self._with_memory_authority(
            agent_id,
            tuple(capsule.authoritative_artifacts),
        )
        if artifacts == tuple(capsule.authoritative_artifacts):
            return capsule
        return replace(capsule, authoritative_artifacts=artifacts)


__all__ = ("MemoryAwareContextCompiler",)
