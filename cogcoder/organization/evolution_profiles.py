from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .registry import AgentRegistry
from .self_model import SelfModelRegistry
from .types import AgentRank, canonical_digest


@dataclass(frozen=True, slots=True)
class EvolutionProfile:
    agent_id: str
    region: str
    rank: AgentRank
    memory_namespace: str
    skill_namespace: str
    learning_capable: bool
    physical_parameters: int
    neural_version: str
    self_model_version: str
    specialization_signature: str

    def to_state(self) -> dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'region': self.region,
            'rank': self.rank.value,
            'memory_namespace': self.memory_namespace,
            'skill_namespace': self.skill_namespace,
            'learning_capable': self.learning_capable,
            'physical_parameters': self.physical_parameters,
            'neural_version': self.neural_version,
            'self_model_version': self.self_model_version,
            'specialization_signature': self.specialization_signature,
        }


class EvolutionProfileRegistry:
    def __init__(self, *, registry: AgentRegistry, self_models: SelfModelRegistry) -> None:
        self.registry = registry
        self.self_models = self_models

    @staticmethod
    def _specialization_signature(identity) -> str:
        return canonical_digest({
            'agent_id': identity.agent_id,
            'region': identity.region,
            'role': identity.role,
            'rank': identity.rank.value,
            'memory_namespace': identity.memory_namespace,
            'skill_namespace': identity.skill_namespace,
            'specialization_version': identity.specialization_version,
            'cognitive_capabilities': list(identity.cognitive_capabilities),
            'external_core_bindings': list(identity.external_core_bindings),
            'tool_permissions': list(identity.tool_permissions),
            'authority_scope': list(identity.authority_scope),
            'parameter_accounting': identity.parameter_accounting.to_state(),
        })

    def get(self, agent_id: str) -> EvolutionProfile:
        identity = self.registry.get(agent_id)
        self_model = self.self_models.get(agent_id)
        return EvolutionProfile(
            agent_id=identity.agent_id,
            region=identity.region,
            rank=identity.rank,
            memory_namespace=identity.memory_namespace,
            skill_namespace=identity.skill_namespace,
            learning_capable=identity.learning_capable,
            physical_parameters=identity.parameter_accounting.total_physical_parameters,
            neural_version=identity.neural_version,
            self_model_version=self_model.version,
            specialization_signature=self._specialization_signature(identity),
        )

    def profiles(self) -> tuple[EvolutionProfile, ...]:
        return tuple(self.get(identity.agent_id) for identity in self.registry.identities())

    def to_state(self) -> dict[str, Any]:
        return {'profiles': [row.to_state() for row in self.profiles()]}

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        self_models: SelfModelRegistry,
        state: Mapping[str, Any],
    ) -> 'EvolutionProfileRegistry':
        result = cls(registry=registry, self_models=self_models)
        expected = {row.agent_id: row for row in result.profiles()}
        for raw in state.get('profiles', ()):
            agent_id = str(raw['agent_id'])
            current = expected.get(agent_id)
            if current is None:
                raise ValueError(f'evolution profile references unknown agent: {agent_id}')
            if str(raw.get('specialization_signature', '')) != current.specialization_signature:
                raise ValueError(f'evolution specialization signature drift for {agent_id}')
            if str(raw.get('memory_namespace', '')) != current.memory_namespace:
                raise ValueError(f'evolution memory namespace drift for {agent_id}')
            if str(raw.get('skill_namespace', '')) != current.skill_namespace:
                raise ValueError(f'evolution skill namespace drift for {agent_id}')
        return result
