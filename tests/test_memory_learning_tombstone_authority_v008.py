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


def _v2_tombstone_payload(state: dict[str, object]) -> dict[str, object]:
    return {
        "schema": state["schema"],
        "memory_id": state["memory_id"],
        "content_digest": state["content_digest"],
        "archive_receipt_id": state["archive_receipt_id"],
        "actor_agent_id": state["actor_agent_id"],
        "reason": state["reason"],
        "evidence_refs": state["evidence_refs"],
    }


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

    with pytest.raises(ValueError, match="tombstone.*archive|archive.*tombstone|forget"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_forget_rejects_new_semantics_for_already_archived_memory() -> None:
    substrate = _substrate()
    row = _remember_verified(substrate)
    substrate.lifecycle.transition(
        row.memory_id,
        actor_agent_id="memory.worker",
        new_status=MemoryStatus.ARCHIVED,
        reason="retention_window_elapsed",
        evidence_refs=("evidence-retention",),
    )

    with pytest.raises(ValueError, match="archive.*authority|forget.*archive|already archived"):
        substrate.forget(
            row.memory_id,
            actor_agent_id="memory.worker",
            reason="different_forgetting_reason",
            evidence_refs=("evidence-different-forgetting",),
        )

    with pytest.raises(KeyError, match="tombstone"):
        substrate.tombstone(row.memory_id)


def test_forget_emits_content_addressed_tombstone_bound_to_exact_archive_receipt() -> None:
    substrate = _substrate()
    row = _remember_verified(substrate)
    tombstone = substrate.forget(
        row.memory_id,
        actor_agent_id="memory.worker",
        reason="governed_forgetting",
        evidence_refs=("evidence-forgetting",),
    )
    archive_receipt = substrate.lifecycle.receipts_for(row.memory_id)[-1]
    tombstone_state = tombstone.to_state()

    assert tombstone_state["schema"] == "memory-tombstone-v2"
    assert tombstone_state["archive_receipt_id"] == archive_receipt.receipt_id
    assert tombstone_state["actor_agent_id"] == archive_receipt.actor_agent_id == "memory.worker"
    assert tombstone_state["reason"] == archive_receipt.reason
    assert tuple(tombstone_state["evidence_refs"]) == archive_receipt.evidence_refs
    assert tombstone_state["tombstone_id"] == canonical_digest(_v2_tombstone_payload(tombstone_state))

    state = substrate.to_state()
    tampered = dict(state["tombstones"][0])
    tampered["archive_receipt_id"] = "memory-lifecycle-99999999"
    tampered["tombstone_id"] = canonical_digest(_v2_tombstone_payload(tampered))
    state["tombstones"] = [tampered]

    with pytest.raises(ValueError, match="tombstone.*receipt|archive.*receipt|forget"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)
