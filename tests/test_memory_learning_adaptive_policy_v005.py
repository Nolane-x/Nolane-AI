from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.memory.fabric import MemoryScope, MemoryStatus
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


def test_retrieval_policy_identity_is_content_addressed_roundtrips_and_migrates() -> None:
    from nolane.memory.adaptive_policy import MemoryRetrievalPolicy

    policy = MemoryRetrievalPolicy(cost_weight=0.75, information_weight=1.25, max_estimated_units=12)
    same = MemoryRetrievalPolicy.from_state(policy.to_state())
    changed = MemoryRetrievalPolicy(cost_weight=0.25, information_weight=1.25, max_estimated_units=12)
    migrated = policy.migrate(cost_weight=1.5, max_estimated_units=9)

    assert same == policy
    assert same.policy_id == policy.policy_id
    assert changed.policy_id != policy.policy_id
    assert migrated.parent_policy_id == policy.policy_id
    assert migrated.policy_id != policy.policy_id
    assert migrated.cost_weight == 1.5
    assert migrated.max_estimated_units == 9
    assert MemoryRetrievalPolicy.from_state(migrated.to_state()) == migrated


def test_retrieval_policy_is_cost_sensitive_but_keeps_hard_authority_filters() -> None:
    from nolane.memory.adaptive_policy import MemoryRetrievalPolicy
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    short = remember_verified(substrate, evidence_id='evidence-short', text="verified concise anchor", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC, confidence=0.9, salience=0.7, tags=("anchor",))
    long = remember_verified(substrate, evidence_id='evidence-long', text="verified verbose anchor " + ("detail " * 160), owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC, confidence=0.9, salience=0.7, tags=("anchor",))
    unverified = substrate.remember(
        text="cheap but unverified anchor",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.HYPOTHESIS,
        tags=("anchor",),
    )

    policy = MemoryRetrievalPolicy(cost_weight=8.0, information_weight=1.0, max_estimated_units=8)
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-30T00:00:00+00:00",
        tags=("anchor",),
        limit=2,
        policy=policy,
    )

    assert tuple(item.memory.memory_id for item in bundle.selected) == (short.memory_id,)
    rejected = dict(bundle.rejected)
    assert rejected[long.memory_id] == "policy_cost_budget"
    assert rejected[unverified.memory_id] == MemoryStatus.QUARANTINED.value
    assert bundle.receipt.policy_id == policy.policy_id
    assert bundle.receipt.selected_memory_ids == (short.memory_id,)
    assert bundle.receipt.memory_state_digest


def test_compaction_preserves_epistemic_type_and_raw_reconstructability() -> None:
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    first = remember_verified(substrate, evidence_id='evidence-a', text="anchor A verified under source receipt A", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC, source_refs=("source-a",))
    second = remember_verified(substrate, evidence_id='evidence-b', text="anchor B verified under source receipt B", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC, source_refs=("source-b",))

    compacted, receipt = substrate.compact(
        source_memory_ids=(first.memory_id, second.memory_id),
        summary_text="A and B are the current verified anchors.",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        actor_agent_id="memory.worker",
        evidence_refs=("compaction-review",),
    )

    assert substrate.metadata(compacted.memory_id).epistemic_type is EpistemicType.VERIFIED
    assert substrate.memory.get(first.memory_id).status is MemoryStatus.ACTIVE
    assert substrate.memory.get(second.memory_id).status is MemoryStatus.ACTIVE
    assert receipt.source_memory_ids == tuple(sorted((first.memory_id, second.memory_id)))
    reconstructed = substrate.reconstruct_compaction(receipt.compaction_id)
    assert tuple(row.memory_id for row in reconstructed) == receipt.source_memory_ids


def test_compaction_rejects_mixed_epistemic_types() -> None:
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    verified = remember_verified(substrate, evidence_id='evidence-v', text="verified state", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC)
    hypothesis = substrate.remember(
        text="hypothesis state",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.HYPOTHESIS,
    )

    with pytest.raises(ValueError, match="epistemic type"):
        substrate.compact(
            source_memory_ids=(verified.memory_id, hypothesis.memory_id),
            summary_text="unsafe mixed summary",
            owner_agent_id="memory.chief",
            scope=MemoryScope.PERSONAL,
            kind=MemoryKind.SEMANTIC,
            actor_agent_id="memory.worker",
            evidence_refs=("review",),
        )


def test_unhealthy_anchor_is_fail_closed_and_persists_across_restart() -> None:
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    anchor = remember_verified(substrate, evidence_id='schema-v4', text="API v4 schema anchor", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.PROJECT_STATE, version_scope="v4")
    substrate.record_anchor_health(
        anchor.memory_id,
        actor_agent_id="memory.worker",
        healthy=False,
        evidence_ref="schema-v5-drift",
        observed_version_scope="v5",
        reason="bound version no longer matches live environment",
    )

    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-30T00:00:00+00:00",
    )
    assert dict(bundle.rejected)[anchor.memory_id] == "anchor_unhealthy"

    state = substrate.to_state()
    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))
    restored_bundle = restored.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-30T00:00:00+00:00",
    )
    assert restored.to_state() == state
    assert dict(restored_bundle.rejected)[anchor.memory_id] == "anchor_unhealthy"


def test_anchor_health_cannot_be_self_certified() -> None:
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    anchor = remember_verified(substrate, evidence_id='schema-v4', text="self-owned anchor", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.PROJECT_STATE)

    with pytest.raises(PermissionError, match="external"):
        substrate.record_anchor_health(
            anchor.memory_id,
            actor_agent_id="memory.chief",
            healthy=True,
            evidence_ref="self-check",
            observed_version_scope="v4",
            reason="self-certified",
        )


def test_retrieval_policy_registry_persists_for_receipt_audit() -> None:
    from nolane.memory.adaptive_policy import MemoryRetrievalPolicy
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    remember_verified(substrate, evidence_id='evidence-audit', text="auditable verified anchor", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC)
    policy = MemoryRetrievalPolicy(information_weight=1.5, cost_weight=0.4, max_estimated_units=16)
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-30T00:00:00+00:00",
        policy=policy,
    )

    state = substrate.to_state()
    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))

    assert restored.retrieval_policy(bundle.receipt.policy_id) == policy
    assert restored.retrieval_receipt(bundle.receipt.receipt_id) == bundle.receipt
    assert restored.to_state() == state


def test_anchor_health_state_serializes_in_global_sequence_order() -> None:
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    first = remember_verified(substrate, evidence_id='evidence-first', text="first anchor", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.PROJECT_STATE)
    second = remember_verified(substrate, evidence_id='evidence-second', text="second anchor", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.PROJECT_STATE)

    substrate.record_anchor_health(
        second.memory_id,
        actor_agent_id="memory.worker",
        healthy=True,
        evidence_ref="health-second",
        observed_version_scope=None,
        reason="second observed first",
    )
    substrate.record_anchor_health(
        first.memory_id,
        actor_agent_id="memory.worker",
        healthy=True,
        evidence_ref="health-first",
        observed_version_scope=None,
        reason="first observed second",
    )

    state = substrate.to_state()
    assert [row["sequence"] for row in state["anchor_health"]] == [1, 2]
    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))
    assert restored.to_state() == state


def test_restore_rejects_semantically_rehashed_self_certified_anchor() -> None:
    from nolane.memory.adaptive_policy import MemoryAnchorHealthReceipt
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    anchor = remember_verified(substrate, evidence_id='anchor-evidence', text="externally checked anchor", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.PROJECT_STATE)
    substrate.record_anchor_health(
        anchor.memory_id,
        actor_agent_id="memory.worker",
        healthy=True,
        evidence_ref="external-health",
        observed_version_scope=None,
        reason="external observation",
    )
    state = substrate.to_state()
    original = substrate.anchor_health(anchor.memory_id)[0]
    state["anchor_health"][0] = MemoryAnchorHealthReceipt(
        sequence=original.sequence,
        memory_id=original.memory_id,
        actor_agent_id="memory.chief",
        healthy=original.healthy,
        evidence_ref=original.evidence_ref,
        observed_version_scope=original.observed_version_scope,
        reason="rehash after self-certification",
    ).to_state()

    with pytest.raises(PermissionError, match="external"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))


def test_restore_rejects_semantically_rehashed_self_certified_compaction() -> None:
    from nolane.memory.adaptive_policy import MemoryCompactionReceipt
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    first = remember_verified(substrate, evidence_id='source-one', text="compaction source one", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC)
    second = remember_verified(substrate, evidence_id='source-two', text="compaction source two", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC)
    _, receipt = substrate.compact(
        source_memory_ids=(first.memory_id, second.memory_id),
        summary_text="compacted result",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        actor_agent_id="memory.worker",
        evidence_refs=("external-review",),
    )
    state = substrate.to_state()
    state["compactions"][0] = MemoryCompactionReceipt(source_memory_ids=receipt.source_memory_ids, compacted_memory_id=receipt.compacted_memory_id, source_digest=receipt.source_digest, epistemic_type=receipt.epistemic_type, actor_agent_id="memory.chief", evidence_refs=receipt.evidence_refs, compacted_digest=receipt.compacted_digest).to_state()

    with pytest.raises(PermissionError, match="external"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))


def test_restore_rejects_retrieval_selected_rejected_overlap() -> None:
    from nolane.memory.adaptive_policy import MemoryRetrievalReceipt
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    memory = remember_verified(substrate, evidence_id='retrieval-integrity', text="retrieval receipt integrity anchor", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC)
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-30T00:00:00+00:00",
    )
    state = substrate.to_state()
    receipt = bundle.receipt
    state["retrieval_receipts"][0] = MemoryRetrievalReceipt(policy_id=receipt.policy_id, query_digest=receipt.query_digest, memory_state_digest=receipt.memory_state_digest, selected_memory_ids=receipt.selected_memory_ids, rejected=((memory.memory_id, "budget"),), estimated_units=receipt.estimated_units, query=receipt.query).to_state()

    with pytest.raises(ValueError, match="selected.*rejected|overlap"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))


def test_restore_rejects_tombstone_content_rebinding() -> None:
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    memory = remember_verified(substrate, evidence_id='raw-evidence', text="raw content bound to tombstone", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC)
    forget_memory(substrate, memory.memory_id, actor_agent_id="memory.worker", reason="intentional archival", evidence_id='forget-review')
    state = substrate.to_state()
    state["tombstones"][0]["content_digest"] = "0" * 64

    with pytest.raises(ValueError, match="tombstone.*digest|content"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))


def test_restore_rejects_duplicate_learning_metadata_rows() -> None:
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    remember_verified(substrate, evidence_id='metadata-evidence', text="duplicate metadata sentinel", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC)
    state = substrate.to_state()
    state["metadata"].append(dict(state["metadata"][0]))

    with pytest.raises(ValueError, match="duplicate.*metadata"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))


def test_migrated_retrieval_policy_requires_reconstructible_parent_lineage() -> None:
    from nolane.memory.adaptive_policy import MemoryRetrievalPolicy
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    remember_verified(substrate, evidence_id='policy-lineage', text="policy lineage anchor", owner_agent_id="memory.chief", scope=MemoryScope.PERSONAL, kind=MemoryKind.SEMANTIC)
    parent = MemoryRetrievalPolicy(cost_weight=0.25)
    child = parent.migrate(cost_weight=0.5)

    with pytest.raises(ValueError, match="parent"):
        substrate.retrieve(
            agent_id="memory.chief",
            region="memory-context-knowledge",
            as_of="2026-08-30T00:00:00+00:00",
            policy=child,
        )

    substrate.register_retrieval_policy(parent)
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-30T00:00:00+00:00",
        policy=child,
    )
    assert substrate.retrieval_policy(child.policy_id) == child
    state = substrate.to_state()
    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state, learning_authority=authority_copy(substrate))
    assert restored.retrieval_policy(bundle.receipt.policy_id) == child
