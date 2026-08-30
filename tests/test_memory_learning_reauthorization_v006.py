from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.fabric import MemoryScope, MemoryStatus
from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind
from nolane.memory.skills import SkillScope


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
    return substrate.remember(
        text="verified durable anchor",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("evidence-anchor",),
    )


def _promoted_skill_state() -> tuple[LearningSubstrate, dict]:
    substrate = _substrate()
    skill = substrate.skills.propose(
        owner_agent_id="memory.chief",
        region="memory-context-knowledge",
        name="proof-bounded-skill",
        body="promote only from independent regression and causal evidence",
    )
    substrate.skills.verify(
        skill.skill_id,
        EvidenceRecord("skill-verifier", "memory.worker", True, false_accepts=0, regressions=0),
    )
    substrate.record_skill_validation(
        skill.skill_id,
        regression_evidence_ids=("reg-a", "reg-b"),
        causal_ablation_evidence_ids=("causal-a",),
        regression_evidence_families={"reg-a": "reg-family-a", "reg-b": "reg-family-b"},
        causal_ablation_evidence_families={"causal-a": "causal-family-a"},
    )
    substrate.promote_skill(skill.skill_id, SkillScope.PERSONAL)
    return substrate, substrate.to_state()


def test_tombstone_is_hard_retrieval_deny_even_if_memory_status_drifts_active() -> None:
    substrate = _substrate()
    row = _verified_memory(substrate)
    substrate.forget(
        row.memory_id,
        actor_agent_id="memory.worker",
        reason="explicit_forgetting",
        evidence_refs=("forget-proof",),
    )

    # Simulate a lower-level status drift. A tombstone is a terminal deny marker,
    # not merely a convenience alias for ARCHIVED status.
    substrate.memory.set_status(row.memory_id, MemoryStatus.ACTIVE, reason="unsafe drift")

    bundle = substrate.retrieve(
        agent_id="memory.chief",
        region="memory-context-knowledge",
        as_of="2026-08-30T00:00:00+00:00",
    )

    assert tuple(item.memory.memory_id for item in bundle.selected) == ()
    assert dict(bundle.rejected)[row.memory_id] == "tombstoned"


def test_restore_rejects_tombstone_without_archived_lifecycle_authority() -> None:
    substrate = _substrate()
    row = _verified_memory(substrate)
    substrate.forget(
        row.memory_id,
        actor_agent_id="memory.worker",
        reason="explicit_forgetting",
        evidence_refs=("forget-proof",),
    )
    state = substrate.to_state()

    # Strip the archival proof and rebind the memory to ACTIVE while retaining
    # the tombstone. Restore must not accept this split-brain state.
    state["memory"]["entries"][0]["status"] = MemoryStatus.ACTIVE.value
    state["memory"]["entries"][0]["status_reason"] = None
    state["lifecycle"] = {"receipts": [], "counter": 0}

    with pytest.raises(ValueError, match="tombstone.*archiv|archiv.*tombstone"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_forget_reauthorizes_actor_even_when_memory_was_already_archived() -> None:
    substrate = _substrate()
    row = _verified_memory(substrate)
    substrate.lifecycle.transition(
        row.memory_id,
        actor_agent_id="memory.worker",
        new_status=MemoryStatus.ARCHIVED,
        reason="retention_window_closed",
        evidence_refs=("archive-proof",),
    )

    with pytest.raises(PermissionError, match="Memory/Context|memory lifecycle|forget"):
        substrate.forget(
            row.memory_id,
            actor_agent_id="coding.worker",
            reason="unauthorized_forgetting",
            evidence_refs=("delete-proof",),
        )


def test_restore_rejects_promoted_skill_with_laundered_validation_families() -> None:
    _, state = _promoted_skill_state()
    validation = state["skill_validations"][0]
    validation["regression_evidence_families"] = [
        ["reg-a", "same-family"],
        ["reg-b", "same-family"],
    ]

    with pytest.raises((ValueError, PermissionError), match="independent regression evidence families"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_restore_rejects_promoted_skill_validation_with_incomplete_family_coverage() -> None:
    _, state = _promoted_skill_state()
    validation = state["skill_validations"][0]
    validation["regression_evidence_families"] = [["reg-a", "reg-family-a"]]

    with pytest.raises((ValueError, PermissionError), match="exactly cover|family"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_restore_rejects_active_learning_memory_without_verification_proof() -> None:
    substrate = _substrate()
    substrate.remember(
        text="unverified candidate fact",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.HYPOTHESIS,
    )
    state = substrate.to_state()
    state["memory"]["entries"][0]["status"] = MemoryStatus.ACTIVE.value
    state["memory"]["entries"][0]["status_reason"] = None
    state["metadata"][0]["epistemic_type"] = EpistemicType.VERIFIED.value

    with pytest.raises(ValueError, match="active.*verification|verification.*active|proof"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_restore_rejects_active_nonverified_learning_metadata() -> None:
    substrate = _substrate()
    _verified_memory(substrate)
    state = substrate.to_state()
    state["metadata"][0]["epistemic_type"] = EpistemicType.INFERENCE.value

    with pytest.raises(ValueError, match="active.*verified|verified.*active"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_restore_accepts_revalidated_memory_with_lifecycle_verification_proof() -> None:
    substrate = _substrate()
    row = substrate.remember(
        text="candidate fact awaiting review",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.HYPOTHESIS,
    )
    substrate.validate_memory(
        row.memory_id,
        actor_agent_id="memory.chief",
        evidence_refs=("external-review",),
        correction_ref="correction-proof",
    )

    state = substrate.to_state()
    restored = LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)

    assert restored.to_state() == state
    assert restored.memory.get(row.memory_id).status is MemoryStatus.ACTIVE
    assert restored.metadata(row.memory_id).epistemic_type is EpistemicType.VERIFIED
