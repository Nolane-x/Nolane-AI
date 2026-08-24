from __future__ import annotations

from typing import Any, Mapping

from nolane.schemas.identity import AgentStatus
from cogcoder.organization.types import CognitiveEvent, EventKind

from .events import EventLedger
from .identity import AgentRegistry

COMPONENT_ID = "organization.lifecycle"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.scheduler"


class WakeSleepScheduler:
    """Canonical persistent wake/sleep/checkpoint lifecycle scheduler."""

    def __init__(self, *, registry: AgentRegistry, ledger: EventLedger) -> None:
        self.registry = registry
        self.ledger = ledger
        self._checkpoints: dict[str, str | None] = {}
        self._wake_reasons: dict[str, set[str]] = {}
        self._periodic_tokens: dict[str, int] = {}

    def sleep(self, agent_id: str, *, checkpoint_event_id: str | None = None) -> None:
        identity = self.registry.get(agent_id)
        if checkpoint_event_id is not None:
            self.ledger.get(checkpoint_event_id)
        checkpoint = self.ledger.append(
            EventKind.AGENT_CHECKPOINTED,
            source_agent_id=str(agent_id),
            target_agent_id=str(agent_id),
            region=identity.region,
            causal_parent_ids=() if checkpoint_event_id is None else (checkpoint_event_id,),
            payload={"previous_event_id": checkpoint_event_id, "current_task": identity.current_task},
        )
        self._checkpoints[str(agent_id)] = checkpoint.event_id
        self.registry.set_checkpoint(agent_id, checkpoint.event_id)
        self.registry.set_status(agent_id, AgentStatus.SLEEPING)
        self.ledger.append(
            EventKind.AGENT_SLEEP,
            source_agent_id=str(agent_id),
            target_agent_id=str(agent_id),
            region=identity.region,
            causal_parent_ids=(checkpoint.event_id,),
            payload={"checkpoint_event_id": checkpoint.event_id},
        )

    def wake(self, agent_id: str, *, reason: str) -> None:
        identity = self.registry.get(agent_id)
        if not str(reason).strip():
            raise ValueError("wake reason must be explicit")
        self.registry.set_status(agent_id, AgentStatus.WAKING)
        checkpoint = self._checkpoints.get(str(agent_id))
        self.ledger.append(
            EventKind.AGENT_WAKE,
            source_agent_id=str(agent_id),
            target_agent_id=str(agent_id),
            region=identity.region,
            causal_parent_ids=() if checkpoint is None else (checkpoint,),
            payload={"reason": str(reason), "checkpoint_event_id": checkpoint},
        )
        self.registry.set_status(agent_id, AgentStatus.ACTIVE)
        self._wake_reasons.pop(str(agent_id), None)

    def notify_event(self, event: CognitiveEvent) -> None:
        recipients: set[str] = set()
        if event.target_agent_id is not None:
            recipients.add(event.target_agent_id)
        for identity in self.registry.identities():
            if event in self.ledger.deliverable_for(identity.agent_id):
                recipients.add(identity.agent_id)
        for agent_id in recipients:
            if self.registry.get(agent_id).status is AgentStatus.SLEEPING:
                self._wake_reasons.setdefault(agent_id, set()).add(f"event:{event.event_id}")

    def schedule_periodic_wake(self, agent_id: str, *, token: int) -> None:
        self.registry.get(agent_id)
        if token < 0:
            raise ValueError("periodic token must be non-negative")
        self._periodic_tokens[str(agent_id)] = int(token)

    def tick(self, token: int) -> None:
        for agent_id, due in tuple(self._periodic_tokens.items()):
            if token >= due and self.registry.get(agent_id).status is AgentStatus.SLEEPING:
                self._wake_reasons.setdefault(agent_id, set()).add(f"periodic:{due}")

    def due_agents(self) -> tuple[str, ...]:
        return tuple(sorted(self._wake_reasons))

    def wake_reasons(self, agent_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._wake_reasons.get(str(agent_id), ())))

    def checkpoint_for(self, agent_id: str) -> str | None:
        identity = self.registry.get(agent_id)
        return self._checkpoints.get(str(agent_id), identity.checkpoint_id)

    def to_state(self) -> dict[str, Any]:
        return {
            "checkpoints": dict(sorted(self._checkpoints.items())),
            "wake_reasons": {key: sorted(value) for key, value in sorted(self._wake_reasons.items())},
            "periodic_tokens": dict(sorted(self._periodic_tokens.items())),
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        ledger: EventLedger,
        state: Mapping[str, Any],
    ) -> "WakeSleepScheduler":
        scheduler = cls(registry=registry, ledger=ledger)
        scheduler._checkpoints = {
            str(key): None if value is None else str(value)
            for key, value in state.get("checkpoints", {}).items()
        }
        scheduler._wake_reasons = {
            str(key): {str(value) for value in values}
            for key, values in state.get("wake_reasons", {}).items()
        }
        scheduler._periodic_tokens = {
            str(key): int(value)
            for key, value in state.get("periodic_tokens", {}).items()
        }
        for agent_id, checkpoint in scheduler._checkpoints.items():
            registry.set_checkpoint(agent_id, checkpoint)
        return scheduler


__all__ = (
    "WakeSleepScheduler",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
