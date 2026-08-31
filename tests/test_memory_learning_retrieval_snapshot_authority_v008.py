from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.adaptive_policy import MemoryRetrievalReceipt
from nolane.memory.fabric import MemoryScope
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


def _remember_private_verified(
    substrate: LearningSubstrate,
    *,
    owner_agent_id: str,
    text: str,
    evidence_id: str,
):
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

    # A self-consistent snapshot+receipt pair is not authoritative if it rewrites
    # immutable Memory Fabric identity. Otherwise a private memory can be forged
    # into another agent's historical visibility frontier and replay cleanly.
    with pytest.raises(ValueError, match="retrieval replay snapshot.*authority|immutable.*memory"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)
