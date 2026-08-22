from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable, Mapping

from .types import AgentIdentity, AgentStatus


class AgentRegistry:
    def __init__(self, identities: Iterable[AgentIdentity] = ()) -> None:
        self._rows: dict[str, AgentIdentity] = {}
        self._accepted_versions: dict[str, list[str]] = {}
        for identity in identities:
            self.register(identity)

    def register(self, identity: AgentIdentity) -> None:
        if identity.agent_id in self._rows:
            raise ValueError(f'duplicate agent id: {identity.agent_id}')
        self._rows[identity.agent_id] = identity
        self._accepted_versions[identity.agent_id] = [identity.neural_version]

    def get(self, agent_id: str) -> AgentIdentity:
        try:
            return self._rows[str(agent_id)]
        except KeyError as exc:
            raise KeyError(f'unknown agent id: {agent_id}') from exc

    def identities(self) -> tuple[AgentIdentity, ...]:
        return tuple(self._rows.values())

    def set_status(self, agent_id: str, status: AgentStatus) -> AgentIdentity:
        old = self.get(agent_id)
        row = replace(old, status=AgentStatus(status))
        self._rows[row.agent_id] = row
        return row

    def bind_task(self, agent_id: str, task_id: str | None) -> AgentIdentity:
        old = self.get(agent_id)
        row = replace(old, current_task=None if task_id is None else str(task_id))
        self._rows[row.agent_id] = row
        return row

    def set_checkpoint(self, agent_id: str, checkpoint_id: str | None) -> AgentIdentity:
        old = self.get(agent_id)
        row = replace(old, checkpoint_id=None if checkpoint_id is None else str(checkpoint_id))
        self._rows[row.agent_id] = row
        return row

    def set_self_model_version(self, agent_id: str, self_model_version: str) -> AgentIdentity:
        version = str(self_model_version).strip()
        if not version:
            raise ValueError('self-model version must be non-empty')
        old = self.get(agent_id)
        row = replace(old, self_model_version=version)
        self._rows[row.agent_id] = row
        return row

    def accept_neural_version(self, agent_id: str, neural_version: str) -> AgentIdentity:
        version = str(neural_version).strip()
        if not version:
            raise ValueError('accepted neural version must be non-empty')
        old = self.get(agent_id)
        row = replace(old, neural_version=version)
        self._rows[row.agent_id] = row
        history = self._accepted_versions.setdefault(row.agent_id, [])
        if version not in history:
            history.append(version)
        return row

    def accepted_versions(self, agent_id: str) -> tuple[str, ...]:
        self.get(agent_id)
        return tuple(self._accepted_versions[agent_id])

    def to_state(self) -> dict[str, Any]:
        return {
            'identities': [row.to_state() for row in self.identities()],
            'accepted_versions': {key: list(value) for key, value in sorted(self._accepted_versions.items())},
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'AgentRegistry':
        registry = cls(AgentIdentity.from_state(row) for row in state.get('identities', ()))
        accepted = state.get('accepted_versions', {})
        if isinstance(accepted, Mapping):
            for agent_id, versions in accepted.items():
                registry.get(str(agent_id))
                history = [str(version) for version in versions]
                current = registry.get(str(agent_id)).neural_version
                if current not in history:
                    history.append(current)
                registry._accepted_versions[str(agent_id)] = history
        return registry
