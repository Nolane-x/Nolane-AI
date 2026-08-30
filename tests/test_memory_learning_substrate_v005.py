from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.memory.fabric import MemoryFabric, MemoryScope, MemoryStatus


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


def test_fabric_can_create_quarantined_memory_atomically() -> None:
    memory = MemoryFabric()
    row = memory.write(
        MemoryScope.PERSONAL,
        "unverified observation",
        owner_agent_id="memory.chief",
        initial_status=MemoryStatus.QUARANTINED,
        status_reason="awaiting_external_validation",
    )
    assert row.status is MemoryStatus.QUARANTINED
    assert row.status_reason == "awaiting_external_validation"
    assert memory.visible_entries(agent_id="memory.chief", region="memory-context-knowledge") == ()


def test_learning_metadata_preserves_epistemic_type_time_version_and_failure_semantics() -> None:
    from nolane.memory.learning_substrate import EpistemicType, LearningMemoryMetadata, MemoryKind

    metadata = LearningMemoryMetadata(
        memory_id="mem-00000001",
        kind=MemoryKind.FAILURE,
        epistemic_type=EpistemicType.OBSERVATION,
        source_refs=("log://run-7",),
        valid_from="2026-08-30T00:00:00+00:00",
        valid_until="2026-09-30T00:00:00+00:00",
        version_scope=">=4,<5",
        last_verified_ref="evidence-7",
        salience=0.9,
        failure_condition="API v4 removed field legacy_id",
        retry_if_changed="retry only if API major version changes",
    )
    assert LearningMemoryMetadata.from_state(metadata.to_state()) == metadata
    assert metadata.kind is MemoryKind.FAILURE
    assert metadata.epistemic_type is EpistemicType.OBSERVATION


def test_learning_substrate_retrieval_excludes_expired_and_conflicting_lower_authority_memory() -> None:
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind
    from nolane.memory.lifecycle import MemoryRelationKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    old = substrate.remember(
        text="API supports legacy_id",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.INFERENCE,
        evidence_ids=("evidence-old",),
        confidence=0.55,
        valid_until="2026-08-01T00:00:00+00:00",
        version_scope="<4",
    )
    current = substrate.remember(
        text="API v4 removed legacy_id",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-new",),
        confidence=0.99,
        valid_from="2026-08-01T00:00:00+00:00",
        version_scope=">=4",
    )
    substrate.relate(
        actor_agent_id="memory.worker",
        source_memory_id=current.memory_id,
        target_memory_id=old.memory_id,
        kind=MemoryRelationKind.CONTRADICTS,
        evidence_refs=("evidence-new",),
    )
    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-30T00:00:00+00:00",
        limit=8,
    )
    assert tuple(row.memory.memory_id for row in bundle.selected) == (current.memory_id,)
    assert dict(bundle.rejected)[old.memory_id] == "expired"


def test_forgetting_archives_content_but_keeps_tombstone_lineage() -> None:
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    row = substrate.remember(
        text="stale project decision",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.DECISION,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-1",),
    )
    tombstone = substrate.forget(
        row.memory_id,
        actor_agent_id="memory.worker",
        reason="superseded_version",
        evidence_refs=("evidence-2",),
    )
    assert substrate.memory.get(row.memory_id).status is MemoryStatus.ARCHIVED
    assert tombstone.memory_id == row.memory_id
    assert tombstone.content_digest
    assert substrate.tombstone(row.memory_id) == tombstone


def test_skill_persistence_requires_executed_regression_and_causal_ablation_evidence() -> None:
    from nolane.external_core.evidence import EvidenceRecord
    from nolane.memory.learning_substrate import LearningSubstrate
    from nolane.memory.skills import SkillScope

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    skill = substrate.skills.propose(
        owner_agent_id="memory.chief",
        region="memory-context-knowledge",
        name="avoid-stale-anchor",
        body="revalidate anchors before use",
    )
    verifier = EvidenceRecord("evidence-verifier", "memory.worker", True, false_accepts=0, regressions=0)
    substrate.skills.verify(skill.skill_id, verifier)

    with pytest.raises(PermissionError, match="executed regression evidence"):
        substrate.promote_skill(skill.skill_id, SkillScope.PERSONAL)

    substrate.record_skill_validation(
        skill.skill_id,
        regression_evidence_ids=("regression-executed-1",),
        causal_ablation_evidence_ids=("causal-ablation-1",),
    )
    promoted = substrate.promote_skill(skill.skill_id, SkillScope.PERSONAL)
    assert promoted.scope is SkillScope.PERSONAL


def test_learning_substrate_state_roundtrip_is_deterministic() -> None:
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    substrate.remember(
        text="failure under condition C because assumption A contradicted log L",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.FAILURE,
        epistemic_type=EpistemicType.OBSERVATION,
        evidence_ids=("log-L",),
        failure_condition="condition C with assumption A",
        retry_if_changed="retry if A or C changes",
    )
    state = substrate.to_state()
    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)
    assert restored.to_state() == state
