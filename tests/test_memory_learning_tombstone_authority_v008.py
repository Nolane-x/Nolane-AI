from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.fabric import MemoryScope, MemoryStatus
from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind


class _RegistryStub:
    def __init__(self) -> None:
        self._actors = {
            "memory.chief": SimpleNamespace(agent_id="memory.chief", region="memory-context-knowledge"),
            "memory.worker": SimpleNamespace(agent_id="memory.worker", region="memory-context-knowledge"),
        }

    def get(self, agent_id: str):
        return self._actors[str(agent_id)]


class _EventStub:
    def latest_event_id(self):
        return None

    def get(self, event_id: str):
        raise KeyError(event_id)


def _substrate() -> LearningSubstrate:
    return LearningSubstrate(registry=_RegistryStub(), events=_EventStub())


def _remember_verified(substrate: LearningSubstrate):
    return substrate.remember(
        text="verified memory whose archive is not a forgetting authorization",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-memory",),
    )


def test_restore_rejects_tombstone_not_bound_to_archive_authority() -> None:
    substrate = _substrate()
    row = _remember_verified(substrate)
    substrate.lifecycle.transition(
        row.memory_id,
        actor_agent_id="memory.worker",
        new_status=MemoryStatus.ARCHIVED,
        reason="retention_window_elapsed",
        evidence_refs=("evidence-retention",),
    )
    state = substrate.to_state()
    state["tombstones"] = [
        {
            "memory_id": row.memory_id,
            "content_digest": canonical_digest({"memory_id": row.memory_id, "text": row.text}),
            "reason": "forged_forgetting_authority",
            "evidence_refs": ["evidence-forged-forgetting"],
        }
    ]

    # The memory is legitimately archived, but that archive did not authorize the
    # injected forgetting semantics. Restore must bind a tombstone to its exact
    # lifecycle authority rather than accepting any archived state.
    with pytest.raises(ValueError, match="tombstone.*archive|archive.*tombstone|forget"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)
