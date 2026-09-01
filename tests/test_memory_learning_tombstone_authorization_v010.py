from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.fabric import MemoryScope, MemoryStatus
from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind
from nolane.memory.lifecycle import COMPONENT_VERSION as LIFECYCLE_COMPONENT_VERSION
from nolane.metadata.component_versions import component_version
from tests.memory_learning_authority_helpers import admit_memory, authority_copy, forget_memory, remember_verified, verify_skill


class _RegistryStub:
    def __init__(self) -> None:
        self._actors = {
            "memory.chief": SimpleNamespace(agent_id="memory.chief", region="memory-context-knowledge"),
            "memory.worker": SimpleNamespace(agent_id="memory.worker", region="memory-context-knowledge"),
            "coding.worker": SimpleNamespace(agent_id="coding.worker", region="core-coding"),
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
    return remember_verified(substrate, evidence_id='evidence-retention', text="retained archive that was never forgotten", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC)


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
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))


def test_restore_rejects_forged_tombstone_even_with_valid_actor_and_archive_receipt() -> None:
    substrate = _substrate()
    row = _verified_memory(substrate)
    archive = substrate.lifecycle.transition(
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
            "actor_agent_id": "memory.worker",
            "archive_receipt_id": archive.receipt_id,
        }
    ]

    with pytest.raises(ValueError, match="forget.*authorization|authorization.*forget|forget.*receipt"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))


def test_forget_persists_actor_and_exact_archive_receipt_authority() -> None:
    substrate = _substrate()
    row = _verified_memory(substrate)
    tombstone = forget_memory(substrate, row.memory_id, actor_agent_id="memory.worker", reason="explicit governed forgetting", evidence_id='forget-proof')
    archive = substrate.lifecycle.receipts_for(row.memory_id)[-1]
    state = substrate.to_state()

    assert tombstone.actor_agent_id == "memory.worker"
    assert tombstone.archive_receipt_id == archive.receipt_id
    assert tombstone.forget_receipt_id == "memory-forget-00000001"
    assert archive.new_status is MemoryStatus.ARCHIVED
    assert state["forget_counter"] == 1
    assert state["forget_receipts"][0]["receipt_id"] == tombstone.forget_receipt_id
    assert state["forget_receipts"][0]["memory_id"] == row.memory_id
    assert state["forget_receipts"][0]["archive_receipt_id"] == archive.receipt_id

    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))
    assert restored.tombstone(row.memory_id) == tombstone


def test_forget_of_prearchived_memory_binds_existing_terminal_archive_receipt() -> None:
    substrate = _substrate()
    row = _verified_memory(substrate)
    archive = substrate.lifecycle.transition(
        row.memory_id,
        actor_agent_id="memory.worker",
        new_status=MemoryStatus.ARCHIVED,
        reason="retention_window_closed",
        evidence_refs=("archive-proof",),
    )
    receipts_before_forget = substrate.lifecycle.receipts_for(row.memory_id)
    tombstone = forget_memory(substrate, row.memory_id, actor_agent_id="memory.chief", reason="later governed forgetting", evidence_id='forget-proof')

    assert tombstone.actor_agent_id == "memory.chief"
    assert tombstone.archive_receipt_id == archive.receipt_id
    assert tombstone.forget_receipt_id == "memory-forget-00000001"
    assert receipts_before_forget[-1] == archive
    assert substrate.lifecycle.receipts_for(row.memory_id) == receipts_before_forget
    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=substrate.to_state(), learning_authority=authority_copy(substrate))
    assert restored.tombstone(row.memory_id) == tombstone


def test_restore_rejects_tombstone_actor_rebinding_outside_memory_authority() -> None:
    substrate = _substrate()
    row = _verified_memory(substrate)
    forget_memory(substrate, row.memory_id, actor_agent_id="memory.worker", reason="explicit governed forgetting", evidence_id='forget-proof')
    state = substrate.to_state()
    state["tombstones"][0]["actor_agent_id"] = "coding.worker"

    with pytest.raises(PermissionError, match="Memory/Context|tombstone.*actor|forget"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))


def test_restore_rejects_tombstone_archive_receipt_rebinding() -> None:
    substrate = _substrate()
    row = _verified_memory(substrate)
    forget_memory(substrate, row.memory_id, actor_agent_id="memory.worker", reason="explicit governed forgetting", evidence_id='forget-proof')
    state = substrate.to_state()
    state["tombstones"][0]["archive_receipt_id"] = "memory-lifecycle-99999999"

    with pytest.raises(ValueError, match="archived lifecycle authority|archive.*receipt"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))


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

    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=substrate.to_state(), learning_authority=authority_copy(substrate))
    assert restored.memory.get(row.memory_id).status is MemoryStatus.ARCHIVED
    with pytest.raises(KeyError):
        restored.tombstone(row.memory_id)


def test_tombstone_authorization_advances_lifecycle_component_revision() -> None:
    assert LIFECYCLE_COMPONENT_VERSION == "0.0.6"
    assert str(component_version("external.memory.lifecycle")) == "0.0.6"
    assert str(component_version("external.memory.retrieval")) == "0.0.4"
