from __future__ import annotations

from copy import deepcopy
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
            "outside.worker": SimpleNamespace(agent_id="outside.worker", region="software-engineering"),
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


def _remember_verified(substrate: LearningSubstrate, text: str = "tombstone authority anchor"):
    return substrate.remember(
        text=text,
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-memory",),
        confidence=0.9,
        salience=0.8,
    )


def test_restore_rejects_tombstone_inserted_after_unrelated_archive() -> None:
    substrate = _substrate()
    row = _remember_verified(substrate)
    substrate.lifecycle.transition(
        row.memory_id,
        actor_agent_id="memory.worker",
        new_status=MemoryStatus.ARCHIVED,
        reason="archive without forgetting",
        evidence_refs=("evidence-archive",),
    )

    state = deepcopy(substrate.to_state())
    state["tombstones"] = [
        {
            "memory_id": row.memory_id,
            "content_digest": canonical_digest({"memory_id": row.memory_id, "text": row.text}),
            "reason": "forged forgetting after legitimate archive",
            "evidence_refs": ["evidence-forged-forget"],
        }
    ]

    with pytest.raises(ValueError, match="memory tombstone requires forgetting authorization"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)
