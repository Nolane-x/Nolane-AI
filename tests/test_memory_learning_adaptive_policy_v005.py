from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.memory.fabric import MemoryScope, MemoryStatus


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
    short = substrate.remember(
        text="verified concise anchor",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-short",),
        confidence=0.9,
        salience=0.7,
        tags=("anchor",),
    )
    long = substrate.remember(
        text="verified verbose anchor " + ("detail " * 160),
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-long",),
        confidence=0.9,
        salience=0.7,
        tags=("anchor",),
    )
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
    first = substrate.remember(
        text="anchor A verified under source receipt A",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-a",),
        source_refs=("source-a",),
    )
    second = substrate.remember(
        text="anchor B verified under source receipt B",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-b",),
        source_refs=("source-b",),
    )

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
    verified = substrate.remember(
        text="verified state",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-v",),
    )
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
    anchor = substrate.remember(
        text="API v4 schema anchor",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.PROJECT_STATE,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("schema-v4",),
        version_scope="v4",
    )
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
    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)
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
    anchor = substrate.remember(
        text="self-owned anchor",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.PROJECT_STATE,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("schema-v4",),
    )

    with pytest.raises(PermissionError, match="external"):
        substrate.record_anchor_health(
            anchor.memory_id,
            actor_agent_id="memory.chief",
            healthy=True,
            evidence_ref="self-check",
            observed_version_scope="v4",
            reason="self-certified",
        )
