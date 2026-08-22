from __future__ import annotations

from typing import Any, Mapping

from .coordination import CoordinationControlPlane
from .runtime_core import OrganizationRuntime as _OrganizationRuntimeCore


class OrganizationRuntime(_OrganizationRuntimeCore):
    """Add Part-XIII coordination while preserving the accepted runtime core."""

    def __init__(self, *args: Any, coordination: CoordinationControlPlane | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.coordination = coordination or CoordinationControlPlane(
            registry=self.registry,
            events=self.ledger,
            authority=self.authority,
            tasks=self.tasks,
            scheduler=self.scheduler,
        )

    def to_state(self) -> dict[str, Any]:
        state = super().to_state()
        state['coordination'] = self.coordination.to_state()
        return state

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'OrganizationRuntime':
        runtime = super().from_state(state)
        runtime.coordination = CoordinationControlPlane.from_state(
            registry=runtime.registry,
            events=runtime.ledger,
            authority=runtime.authority,
            tasks=runtime.tasks,
            scheduler=runtime.scheduler,
            state=state.get('coordination', {}),
        )
        return runtime
