from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .registry import AgentRegistry


@dataclass(frozen=True, slots=True)
class ExternalCoreSpec:
    core_id: str
    owner_agent_or_region: str
    capabilities: tuple[str, ...]
    input_schema: str
    output_schema: str
    side_effects: tuple[str, ...]
    required_permissions: tuple[str, ...]
    cost_model: str
    failure_modes: tuple[str, ...]
    verification_hooks: tuple[str, ...]
    version: str

    def to_state(self) -> dict[str, Any]:
        return {
            'core_id': self.core_id,
            'owner_agent_or_region': self.owner_agent_or_region,
            'capabilities': list(self.capabilities),
            'input_schema': self.input_schema,
            'output_schema': self.output_schema,
            'side_effects': list(self.side_effects),
            'required_permissions': list(self.required_permissions),
            'cost_model': self.cost_model,
            'failure_modes': list(self.failure_modes),
            'verification_hooks': list(self.verification_hooks),
            'version': self.version,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ExternalCoreSpec':
        return cls(
            core_id=str(state['core_id']),
            owner_agent_or_region=str(state['owner_agent_or_region']),
            capabilities=tuple(str(x) for x in state.get('capabilities', ())),
            input_schema=str(state.get('input_schema', 'mapping')),
            output_schema=str(state.get('output_schema', 'mapping')),
            side_effects=tuple(str(x) for x in state.get('side_effects', ())),
            required_permissions=tuple(str(x) for x in state.get('required_permissions', ())),
            cost_model=str(state.get('cost_model', 'bounded')),
            failure_modes=tuple(str(x) for x in state.get('failure_modes', ())),
            verification_hooks=tuple(str(x) for x in state.get('verification_hooks', ())),
            version=str(state.get('version', '0.1')),
        )


class ExternalCoreRegistry:
    def __init__(self) -> None:
        self._cores: dict[str, ExternalCoreSpec] = {}

    def register(self, spec: ExternalCoreSpec) -> None:
        if not spec.core_id or not spec.owner_agent_or_region:
            raise ValueError('external core identity and owner must be explicit')
        if not spec.capabilities or not spec.failure_modes or not spec.verification_hooks:
            raise ValueError('external core must declare capabilities, failure modes and verification hooks')
        existing = self._cores.get(spec.core_id)
        if existing is not None and existing != spec:
            raise ValueError(f'external core {spec.core_id} already registered differently')
        self._cores[spec.core_id] = spec

    def get(self, core_id: str) -> ExternalCoreSpec:
        try:
            return self._cores[str(core_id)]
        except KeyError as exc:
            raise KeyError(f'unknown external core: {core_id}') from exc

    def specs(self) -> tuple[ExternalCoreSpec, ...]:
        return tuple(self._cores[key] for key in sorted(self._cores))

    def to_state(self) -> dict[str, Any]:
        return {'cores': [row.to_state() for row in self.specs()]}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ExternalCoreRegistry':
        registry = cls()
        for value in state.get('cores', ()):
            registry.register(ExternalCoreSpec.from_state(value))
        return registry


def build_default_external_core_registry(registry: AgentRegistry) -> ExternalCoreRegistry:
    owners: dict[str, list[str]] = {}
    for identity in registry.identities():
        for core_id in identity.external_core_bindings:
            owners.setdefault(core_id, []).append(identity.agent_id)

    result = ExternalCoreRegistry()
    for core_id, agent_ids in sorted(owners.items()):
        identities = [registry.get(agent_id) for agent_id in agent_ids]
        regions = {row.region for row in identities}
        if len(regions) == 1:
            owner = next(iter(regions))
        elif agent_ids == ['nolane.central']:
            owner = 'nolane.central'
        else:
            owner = 'shared-governed-core'
        result.register(
            ExternalCoreSpec(
                core_id=core_id,
                owner_agent_or_region=owner,
                capabilities=(core_id.replace('-', '_'),),
                input_schema='canonical_mapping_v1',
                output_schema='canonical_mapping_v1',
                side_effects=('owner_declares_side_effects_per_call',),
                required_permissions=('external_core.invoke',),
                cost_model='bounded_owner_metered',
                failure_modes=('unavailable', 'invalid_input', 'invalid_output', 'execution_failure'),
                verification_hooks=('input_receipt', 'output_receipt', 'failure_receipt'),
                version='0.1',
            )
        )
    return result
