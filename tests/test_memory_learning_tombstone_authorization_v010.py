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


def _verified_memory(substrate: LearningSubstrate):
    return substrate.remember(
        text="retained archive that was never forgotten",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-retention",),
    )


def test_restore_rejects_forged_tombstone_borrowing_unrelated_archive_authority() -> None:
    substrate = _substrate()
    row = _verified_memory(substrate)
    substrate.lifecycle.transition(
        row.memory_id,
        actor_agent_id="memory.worker",
        new_status=MemoryStatus.ARCHIVED,
        reason="retention_window_closed",
        evidence_refs=("archive-proof",),
    )

    state = substrate.to_state()
    state["tombstones"] = [
        {
            "memory_id": row.memory_id,
            "content_digest": canonical_digest({"memory_id": row.memory_id, "text": row.text}),
            "reason": "forged permanent forgetting",
            "evidence_refs": ["forged-forget-proof"],
        }
    ]

    with pytest.raises(ValueError, match="tombstone.*authorization|authorization.*tombstone|forget.*authority"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_plain_archival_without_tombstone_remains_restorable() -> None:
    substrate = _substrate()
    row = _verified_memory(substrate)
    substrate.lifecycle.transition(
        row.memory_id,
        actor_agent_id="memory.worker",
        new_status=MemoryStatus.ARCHIVED,
        reason="retention_window_closed",
        evidence_refs=("archive-proof",),
    )

    restored = LearningSubstrate.from_state(
        registry=_RegistryStub(), events=_EventStub(), state=substrate.to_state()
    )
    assert restored.memory.get(row.memory_id).status is MemoryStatus.ARCHIVED
    with pytest.raises(KeyError):
        restored.tombstone(row.memory_id)
