from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.adaptive_policy import MemoryRetrievalReceipt
from nolane.memory.fabric import MemoryScope
from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind
from nolane.memory.retrieval import COMPONENT_VERSION as RETRIEVAL_COMPONENT_VERSION
from nolane.metadata.component_versions import component_version


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


def _remember_verified(substrate: LearningSubstrate, text: str = "snapshot authority anchor"):
    return substrate.remember(
        text=text,
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-snapshot-authority",),
        confidence=0.9,
        salience=0.8,
    )


def _rebind_snapshot_receipt(
    state: dict,
    original: MemoryRetrievalReceipt,
    snapshot: dict,
    *,
    selected_memory_ids: tuple[str, ...] | None = None,
    rejected: tuple[tuple[str, str], ...] | None = None,
    estimated_units: int | None = None,
) -> None:
    digest = canonical_digest(snapshot)
    state["retrieval_snapshots"][0] = {
        "memory_state_digest": digest,
        "state": deepcopy(snapshot),
    }
    forged = MemoryRetrievalReceipt(
        policy_id=original.policy_id,
        query_digest=original.query_digest,
        memory_state_digest=digest,
        selected_memory_ids=original.selected_memory_ids if selected_memory_ids is None else selected_memory_ids,
        rejected=original.rejected if rejected is None else rejected,
        estimated_units=original.estimated_units if estimated_units is None else estimated_units,
        query=original.query,
    )
    state["retrieval_receipts"] = [forged.to_state()]


def test_restore_rejects_rehashed_snapshot_with_active_unverified_memory() -> None:
    substrate = _substrate()
    row = _remember_verified(substrate)
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
        limit=1,
    )
    assert bundle.receipt.selected_memory_ids == (row.memory_id,)

    state = substrate.to_state()
    snapshot = deepcopy(state["retrieval_snapshots"][0]["state"])
    assert snapshot["lifecycle"] == state["lifecycle"]
    snapshot["metadata"][0]["epistemic_type"] = EpistemicType.HYPOTHESIS.value
    _rebind_snapshot_receipt(state, bundle.receipt, snapshot)

    with pytest.raises(ValueError, match="active learning memory requires verified epistemic metadata"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_restore_rejects_rehashed_snapshot_without_lifecycle_authority() -> None:
    substrate = _substrate()
    _remember_verified(substrate, "missing lifecycle snapshot")
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
        limit=1,
    )
    state = substrate.to_state()
    snapshot = deepcopy(state["retrieval_snapshots"][0]["state"])
    snapshot.pop("lifecycle")
    _rebind_snapshot_receipt(state, bundle.receipt, snapshot)

    with pytest.raises(ValueError, match="retrieval replay snapshot requires lifecycle authority"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_restore_rejects_snapshot_tombstone_without_archival_lifecycle_authority() -> None:
    substrate = _substrate()
    row = _remember_verified(substrate, "forged historical tombstone")
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
        limit=1,
    )
    state = substrate.to_state()
    snapshot = deepcopy(state["retrieval_snapshots"][0]["state"])

    substrate.forget(
        row.memory_id,
        actor_agent_id="memory.worker",
        reason="later legitimate archive",
        evidence_refs=("evidence-forget",),
    )
    archived_state = substrate.to_state()
    snapshot["memory"] = deepcopy(archived_state["memory"])
    snapshot["tombstones"] = deepcopy(archived_state["tombstones"])
    # Deliberately keep the pre-forget lifecycle ledger. The historical snapshot
    # therefore claims a tombstone without the archival authority that creates it.
    _rebind_snapshot_receipt(
        state,
        bundle.receipt,
        snapshot,
        selected_memory_ids=(),
        rejected=((row.memory_id, "tombstoned"),),
        estimated_units=0,
    )

    with pytest.raises(ValueError, match="memory tombstone requires archived lifecycle authority"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_historical_snapshot_replay_survives_later_live_lifecycle_advance() -> None:
    substrate = _substrate()
    row = _remember_verified(substrate, "historical lifecycle snapshot")
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
        limit=1,
    )
    substrate.decay_memory(
        row.memory_id,
        actor_agent_id="memory.worker",
        reason="later freshness decay",
        evidence_refs=("evidence-decay",),
    )

    restored = LearningSubstrate.from_state(
        registry=_RegistryStub(), events=_EventStub(), state=substrate.to_state()
    )
    assert restored.retrieval_receipt(bundle.receipt.receipt_id) == bundle.receipt


def test_retrieval_snapshot_authority_advances_retrieval_component_revision() -> None:
    assert RETRIEVAL_COMPONENT_VERSION == "0.0.4"
    assert str(component_version("external.memory.retrieval")) == "0.0.4"
    assert str(component_version("external.memory.lifecycle")) == "0.0.5"
