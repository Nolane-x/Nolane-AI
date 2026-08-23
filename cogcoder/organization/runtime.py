from __future__ import annotations

from typing import Any, Mapping

from .campaign import EvaluationCampaignControlPlane
from .runtime_part15 import OrganizationRuntime as _OrganizationRuntimePart15


class OrganizationRuntime(_OrganizationRuntimePart15):
    """Add post-roadmap real-repository evaluation campaign evidence production over Part XV."""

    def __init__(
        self,
        *args: Any,
        evaluation_campaign: EvaluationCampaignControlPlane | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.evaluation_campaign = evaluation_campaign or EvaluationCampaignControlPlane(
            registry=self.registry,
            artifacts=self.artifacts,
            evaluation=self.evaluation_scaling,
        )

    def to_state(self) -> dict[str, Any]:
        state = super().to_state()
        state['evaluation_campaign'] = self.evaluation_campaign.to_state()
        return state

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'OrganizationRuntime':
        runtime = super().from_state(state)
        runtime.evaluation_campaign = EvaluationCampaignControlPlane.from_state(
            registry=runtime.registry,
            artifacts=runtime.artifacts,
            evaluation=runtime.evaluation_scaling,
            state=state.get('evaluation_campaign', {}),
        )
        return runtime
