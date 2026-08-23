from __future__ import annotations

from typing import Any, Mapping

from .foundry import FoundryControlPlane
from .runtime_part13 import OrganizationRuntime as _OrganizationRuntimePart13


class OrganizationRuntime(_OrganizationRuntimePart13):
    """Add Part-XIV ephemeral specialist Foundry over the accepted Part-XIII runtime."""

    def __init__(self, *args: Any, foundry: FoundryControlPlane | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.foundry = foundry or FoundryControlPlane(
            registry=self.registry,
            tasks=self.tasks,
            coordination=self.coordination,
            artifacts=self.artifacts,
            assurance=self.assurance,
            evolution=self.evolution,
            individual_evolution=self.individual_evolution,
        )

    def to_state(self) -> dict[str, Any]:
        state = super().to_state()
        state['foundry'] = self.foundry.to_state()
        return state

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'OrganizationRuntime':
        runtime = super().from_state(state)
        runtime.foundry = FoundryControlPlane.from_state(
            registry=runtime.registry,
            tasks=runtime.tasks,
            coordination=runtime.coordination,
            artifacts=runtime.artifacts,
            assurance=runtime.assurance,
            evolution=runtime.evolution,
            individual_evolution=runtime.individual_evolution,
            state=state.get('foundry', {}),
        )
        return runtime
