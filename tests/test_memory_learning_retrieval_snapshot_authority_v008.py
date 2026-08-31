from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.adaptive_policy import MemoryRetrievalReceipt
from nolane.memory.fabric import MemoryScope
from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind
from nolane.memory.lifecycle import MemoryRelationKind


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


def _remember_private_verified(substrate: LearningSubstrate, *, owner_agent_id: str, text: str, evidence_id: str):
    return substrate.remember(
        text=text,
        owner_agent_id=owner_agent_id,
        scope=MemoryScope.PRIVATE,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=(evidence_id,),
        confidence=0.9,
        salience=0.8,
    )


def test_restore_rejects_rehashed_snapshot_that_rebinds_private_memory_owner() -> None:
    substrate = _substrate()
    private = _remember_private_verified(
        substrate,
        owner_agent_id="memory.worker",
        text="worker private invariant",
        evidence_id="evidence-worker-private",
    )
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
        limit=1,
    )
    assert private.memory_id not in bundle.receipt.selected_memory_ids
    assert private.memory_id not in dict(bundle.receipt.rejected)
    assert bundle.receipt.query is not None

    state = substrate.to_state()
    snapshot_row = state["retrieval_snapshots"][0]
    snapshot = snapshot_row["state"]
    snapshot["memory"]["entries"][0]["owner_agent_id"] = "memory.chief"
    forged_state_digest = canonical_digest(snapshot)
    snapshot_row["memory_state_digest"] = forged_state_digest
    policy = substrate.retrieval_policy(bundle.receipt.policy_id)
    forged = MemoryRetrievalReceipt(
        policy_id=bundle.receipt.policy_id,
        query_digest=bundle.receipt.query_digest,
        memory_state_digest=forged_state_digest,
        selected_memory_ids=(private.memory_id,),
        rejected=(),
        estimated_units=policy.estimate_units(private.text),
        query=bundle.receipt.query,
    )
    state["retrieval_receipts"] = [forged.to_state()]

    with pytest.raises(ValueError, match="retrieval replay snapshot.*authority|immutable.*memory"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def _rehash_single_receipt_state(substrate: LearningSubstrate, state: dict, bundle) -> None:
    snapshot_row = state["retrieval_snapshots"][0]
    forged_state_digest = canonical_digest(snapshot_row["state"])
    snapshot_row["memory_state_digest"] = forged_state_digest
    original = bundle.receipt
    state["retrieval_receipts"] = [
        MemoryRetrievalReceipt(
            policy_id=original.policy_id,
            query_digest=original.query_digest,
            memory_state_digest=forged_state_digest,
            selected_memory_ids=original.selected_memory_ids,
            rejected=original.rejected,
            estimated_units=original.estimated_units,
            query=original.query,
        ).to_state()
    ]


def test_restore_rejects_rehashed_snapshot_that_rewrites_immutable_memory_text() -> None:
    substrate = _substrate()
    row = _remember_private_verified(
        substrate,
        owner_agent_id="memory.chief",
        text="canonical private invariant",
        evidence_id="evidence-canonical-private",
    )
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
        limit=1,
    )
    assert bundle.receipt.selected_memory_ids == (row.memory_id,)

    state = substrate.to_state()
    state["retrieval_snapshots"][0]["state"]["memory"]["entries"][0]["text"] = "forged private invariant"
    _rehash_single_receipt_state(substrate, state, bundle)

    with pytest.raises(ValueError, match="immutable memory authority"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_restore_rejects_rehashed_snapshot_that_rewrites_immutable_metadata() -> None:
    substrate = _substrate()
    row = substrate.remember(
        text="version scoped invariant",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-version",),
        version_scope="runtime-v1",
    )
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
        limit=1,
    )
    assert bundle.receipt.selected_memory_ids == (row.memory_id,)

    state = substrate.to_state()
    state["retrieval_snapshots"][0]["state"]["metadata"][0]["version_scope"] = "forged-runtime-v2"
    _rehash_single_receipt_state(substrate, state, bundle)

    with pytest.raises(ValueError, match="immutable metadata authority"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_historical_snapshot_remains_authoritative_after_later_status_decay() -> None:
    substrate = _substrate()
    row = _remember_private_verified(
        substrate,
        owner_agent_id="memory.chief",
        text="historical active invariant",
        evidence_id="evidence-active",
    )
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
        limit=1,
    )
    substrate.decay_memory(
        row.memory_id,
        actor_agent_id="memory.worker",
        reason="later decay",
        evidence_refs=("evidence-decay",),
    )

    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=substrate.to_state())
    assert restored.retrieval_receipt(bundle.receipt.receipt_id) == bundle.receipt


def test_historical_snapshot_remains_authoritative_before_later_validation() -> None:
    substrate = _substrate()
    row = substrate.remember(
        text="awaiting validation invariant",
        owner_agent_id="memory.worker",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.OBSERVATION,
        source_refs=("source-observation",),
    )
    bundle = substrate.retrieve(
        agent_id="memory.worker",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
        limit=1,
    )
    assert dict(bundle.receipt.rejected)[row.memory_id] == "quarantined"
    substrate.validate_memory(
        row.memory_id,
        actor_agent_id="memory.chief",
        evidence_refs=("evidence-validation",),
        correction_ref="correction-validation",
    )

    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=substrate.to_state())
    assert restored.retrieval_receipt(bundle.receipt.receipt_id) == bundle.receipt


def test_restore_rejects_rehashed_snapshot_that_rewrites_relation_authority() -> None:
    substrate = _substrate()
    first = substrate.remember(
        text="relation source invariant",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-source",),
    )
    second = substrate.remember(
        text="relation target invariant",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-target",),
    )
    substrate.relate(
        actor_agent_id="memory.worker",
        source_memory_id=first.memory_id,
        target_memory_id=second.memory_id,
        kind=MemoryRelationKind.SUPPORTS,
        evidence_refs=("evidence-relation",),
    )
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-31T00:00:00+00:00",
        limit=2,
    )

    state = substrate.to_state()
    relation = state["retrieval_snapshots"][0]["state"]["relations"]["relations"][0]
    relation["evidence_refs"] = ["forged-relation-evidence"]
    payload = {key: value for key, value in relation.items() if key != "digest"}
    relation["digest"] = canonical_digest(payload)
    _rehash_single_receipt_state(substrate, state, bundle)

    with pytest.raises(ValueError, match="relation authority.*append-only prefix"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)
