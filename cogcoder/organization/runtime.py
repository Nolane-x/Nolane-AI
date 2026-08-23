from __future__ import annotations

from typing import Any, Mapping

from .campaign import EvaluationCampaignControlPlane
from .execution import OrganizationExecutionControlPlane
from .runtime_part15 import OrganizationRuntime as _OrganizationRuntimePart15


class OrganizationRuntime(_OrganizationRuntimePart15):
    """Add real-repository campaign evidence and bounded organization execution over Part XV."""

    def __init__(
        self,
        *args: Any,
        evaluation_campaign: EvaluationCampaignControlPlane | None = None,
        execution: OrganizationExecutionControlPlane | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.evaluation_campaign = evaluation_campaign or EvaluationCampaignControlPlane(
            registry=self.registry,
            artifacts=self.artifacts,
            evaluation=self.evaluation_scaling,
        )
        self.execution = execution or OrganizationExecutionControlPlane(
            registry=self.registry,
            tasks=self.tasks,
            context=self.context,
            artifacts=self.artifacts,
            external_cores=self.external_cores,
            coding=self.coding,
        )

    def to_state(self) -> dict[str, Any]:
        state = super().to_state()
        state['evaluation_campaign'] = self.evaluation_campaign.to_state()
        state['execution'] = self.execution.to_state()
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
        runtime.execution = OrganizationExecutionControlPlane.from_state(
            registry=runtime.registry,
            tasks=runtime.tasks,
            context=runtime.context,
            artifacts=runtime.artifacts,
            external_cores=runtime.external_cores,
            coding=runtime.coding,
            state=state.get('execution', {}),
        )
        return runtime
