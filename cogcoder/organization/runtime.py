from __future__ import annotations

from typing import Any, Mapping

from nolane.memory.runtime_binding import (
    bind_runtime_learning_authorities,
    restore_runtime_learning_overlay,
    split_runtime_learning_state,
)

from .campaign import EvaluationCampaignControlPlane
from .execution import OrganizationExecutionControlPlane
from .runtime_part15 import OrganizationRuntime as _OrganizationRuntimePart15
from .types import EventKind


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
        # The historical runtime layers independently constructed several B
        # authorities. Collapse them at the public composition root so every
        # Memory/Learning control plane operates over the same lifecycle,
        # relation, skill and experience objects.
        bind_runtime_learning_authorities(self)
        self._wake_continuity: dict[str, str] = {}
        self.evaluation_campaign = evaluation_campaign or EvaluationCampaignControlPlane(
            registry=self.registry,
            artifacts=self.artifacts,
            evaluation=self.evaluation_scaling,
        )
        self.execution = execution or OrganizationExecutionControlPlane(
            registry=self.registry,
            tasks=self.tasks,
            context=self.memory_context,
            artifacts=self.artifacts,
            external_cores=self.external_cores,
            coding=self.coding,
        )

    def checkpoint_agent(self, agent_id: str) -> str | None:
        scheduler_checkpoint = super().checkpoint_agent(agent_id)
        if scheduler_checkpoint is None:
            return None
        continuity = self.memory_context.capture_continuity(
            agent_id,
            scheduler_checkpoint_event_id=scheduler_checkpoint,
        )
        self._wake_continuity[scheduler_checkpoint] = continuity.checkpoint_id
        return scheduler_checkpoint

    def wake_agent(self, agent_id: str, *, reason: str):
        scheduler_checkpoint = self.scheduler.checkpoint_for(agent_id)
        continuity_checkpoint_id = (
            None
            if scheduler_checkpoint is None
            else self._wake_continuity.get(scheduler_checkpoint)
        )
        self.scheduler.wake(agent_id, reason=reason)
        compiled = self.memory_context.compile_context(
            agent_id,
            continuity_checkpoint_id=continuity_checkpoint_id,
        )
        verified = self.memory_context.verify_context_capsule(compiled.capsule)
        if verified is None:
            raise ValueError('wake context is missing Neural R2.4 compilation provenance')
        if verified != compiled:
            raise ValueError('wake context provenance does not match canonical compilation')
        return verified.capsule

    def to_state(self) -> dict[str, Any]:
        state = super().to_state()
        skill_state, lifecycle_state, retrieval_state = split_runtime_learning_state(
            self.learning_substrate
        )
        # Keep the existing skill-governance section stable and project the
        # adaptive memory overlay into the canonical lifecycle/retrieval owners.
        state['learning_substrate'] = skill_state
        state['memory_learning_lifecycle'] = lifecycle_state
        state['memory_learning_retrieval'] = retrieval_state
        state['wake_continuity'] = dict(sorted(self._wake_continuity.items()))
        state['evaluation_campaign'] = self.evaluation_campaign.to_state()
        state['execution'] = self.execution.to_state()
        return state

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'OrganizationRuntime':
        runtime = super().from_state(state)
        wake_continuity: dict[str, str] = {}
        raw_wake_continuity = state.get('wake_continuity', {})
        if not isinstance(raw_wake_continuity, Mapping):
            raise ValueError('wake continuity state must be a mapping')
        for raw_scheduler_checkpoint, raw_continuity_checkpoint in raw_wake_continuity.items():
            scheduler_checkpoint = str(raw_scheduler_checkpoint)
            continuity_checkpoint = str(raw_continuity_checkpoint)
            event = runtime.ledger.get(scheduler_checkpoint)
            continuity = runtime.memory_context.context_intelligence.checkpoint(
                continuity_checkpoint
            )
            if event.kind is not EventKind.AGENT_CHECKPOINTED:
                raise ValueError('wake continuity references a non-checkpoint scheduler event')
            if continuity.scheduler_checkpoint_event_id != scheduler_checkpoint:
                raise ValueError('wake continuity scheduler checkpoint mismatch')
            if event.target_agent_id != continuity.agent_id:
                raise ValueError('wake continuity agent checkpoint mismatch')
            wake_continuity[scheduler_checkpoint] = continuity_checkpoint
        runtime._wake_continuity = wake_continuity
        runtime.evaluation_campaign = EvaluationCampaignControlPlane.from_state(
            registry=runtime.registry,
            artifacts=runtime.artifacts,
            evaluation=runtime.evaluation_scaling,
            state=state.get('evaluation_campaign', {}),
        )
        runtime.execution = OrganizationExecutionControlPlane.from_state(
            registry=runtime.registry,
            tasks=runtime.tasks,
            context=runtime.memory_context,
            artifacts=runtime.artifacts,
            external_cores=runtime.external_cores,
            coding=runtime.coding,
            state=state.get('execution', {}),
        )
        restore_runtime_learning_overlay(runtime, state)
        return runtime
