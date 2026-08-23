from __future__ import annotations

from typing import Any, Mapping

from .evaluation import EvaluationScalingControlPlane
from .runtime_part14 import OrganizationRuntime as _OrganizationRuntimePart14


class OrganizationRuntime(_OrganizationRuntimePart14):
    """Add Part-XV evaluation/scaling evidence boundary over the accepted Part-XIV runtime."""

    def __init__(
        self,
        *args: Any,
        evaluation_scaling: EvaluationScalingControlPlane | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.evaluation_scaling = evaluation_scaling or EvaluationScalingControlPlane(
            registry=self.registry,
            artifacts=self.artifacts,
        )

    def to_state(self) -> dict[str, Any]:
        state = super().to_state()
        state['evaluation_scaling'] = self.evaluation_scaling.to_state()
        return state

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'OrganizationRuntime':
        runtime = super().from_state(state)
        runtime.evaluation_scaling = EvaluationScalingControlPlane.from_state(
            registry=runtime.registry,
            artifacts=runtime.artifacts,
            state=state.get('evaluation_scaling', {}),
        )
        return runtime
