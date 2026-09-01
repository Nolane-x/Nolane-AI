from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.memory.adaptive_policy import MemoryRetrievalReceipt
from nolane.memory.fabric import MemoryScope
from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind
from tests.memory_learning_authority_helpers import admit_memory, authority_copy, forget_memory, remember_verified, verify_skill


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


def _remember_verified(substrate: LearningSubstrate, text: str, evidence_id: str):
    return remember_verified(substrate, evidence_id=evidence_id, text=text, owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC, confidence=0.9, salience=0.8)


def test_restore_rejects_rehashed_receipt_with_impossible_selected_set() -> None:
    substrate = _substrate()
    first = _remember_verified(substrate, "first verified retrieval anchor", "evidence-first")
    second = _remember_verified(substrate, "second verified retrieval anchor", "evidence-second")
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
        limit=1,
    )

    assert bundle.receipt.selected_memory_ids == (second.memory_id,)
    assert dict(bundle.receipt.rejected)[first.memory_id] == "budget"

    state = substrate.to_state()
    policy = substrate.retrieval_policy(bundle.receipt.policy_id)
    forged = MemoryRetrievalReceipt(
        policy_id=bundle.receipt.policy_id,
        query_digest=bundle.receipt.query_digest,
        memory_state_digest=bundle.receipt.memory_state_digest,
        selected_memory_ids=(first.memory_id,),
        rejected=((second.memory_id, "budget"),),
        estimated_units=policy.estimate_units(first.text),
    )
    state["retrieval_receipts"] = [forged.to_state()]

    # Content-addressing alone is not enough: this forged receipt hashes cleanly,
    # references real memories and a real policy, but contradicts the deterministic
    # retrieval result for the recorded query/state. Restore must replay authority.
    with pytest.raises(ValueError, match="retrieval receipt.*replay|replay.*retrieval receipt"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))


def test_historical_retrieval_receipt_replays_after_live_memory_advances() -> None:
    substrate = _substrate()
    first = _remember_verified(substrate, "historical verified anchor", "evidence-historical")
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
        limit=1,
    )
    _remember_verified(substrate, "later verified anchor", "evidence-later")

    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=substrate.to_state(), learning_authority=authority_copy(substrate))

    assert restored.retrieval_receipt(bundle.receipt.receipt_id) == bundle.receipt
    assert restored.memory.get(first.memory_id) == first


def test_restore_rejects_tampered_retrieval_snapshot() -> None:
    substrate = _substrate()
    _remember_verified(substrate, "snapshot verified anchor", "evidence-snapshot")
    substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
    )
    state = substrate.to_state()
    state["retrieval_snapshots"][0]["state"]["memory"]["entries"][0]["text"] = "tampered snapshot"

    with pytest.raises(ValueError, match="retrieval replay snapshot digest mismatch"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))


def test_restore_rejects_replayable_receipt_without_historical_snapshot() -> None:
    substrate = _substrate()
    _remember_verified(substrate, "missing snapshot anchor", "evidence-missing")
    substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
    )
    state = substrate.to_state()
    state["retrieval_snapshots"] = []

    with pytest.raises(ValueError, match="retrieval receipt replay snapshot is missing"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))


def test_restore_does_not_elevate_legacy_v1_receipt_to_replay_authority() -> None:
    from nolane.memory.adaptive_policy import MemoryRetrievalPolicy

    substrate = _substrate()
    row = _remember_verified(substrate, "legacy receipt anchor", "evidence-legacy")
    policy = substrate.register_retrieval_policy(MemoryRetrievalPolicy())
    legacy = MemoryRetrievalReceipt(
        policy_id=policy.policy_id,
        query_digest="legacy-one-way-query-digest",
        memory_state_digest="legacy-unreplayable-state-digest",
        selected_memory_ids=(row.memory_id,),
        rejected=(),
        estimated_units=policy.estimate_units(row.text),
    )
    state = substrate.to_state()
    state["retrieval_receipts"] = [legacy.to_state()]

    with pytest.raises(ValueError, match="v2 query envelope"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))
