from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.individual_evolution import IndividualEvolutionControlPlane
from nolane.memory.fabric import MemoryFabric, MemoryScope, MemoryStatus
from nolane.memory.lifecycle import MemoryLifecycleLedger
from nolane.memory.skills import SkillEvolutionEngine, SkillScope


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


def _lifecycle_with_reactivation() -> tuple[MemoryLifecycleLedger, MemoryFabric, _RegistryStub, _EventStub]:
    registry = _RegistryStub()
    events = _EventStub()
    memory = MemoryFabric()
    row = memory.write(
        MemoryScope.PERSONAL,
        "governed memory",
        owner_agent_id="memory.chief",
    )
    lifecycle = MemoryLifecycleLedger(registry=registry, memory=memory, events=events)
    lifecycle.transition(
        row.memory_id,
        actor_agent_id="memory.worker",
        new_status=MemoryStatus.STALE,
        reason="freshness_window_elapsed",
        evidence_refs=("evidence-stale",),
    )
    lifecycle.transition(
        row.memory_id,
        actor_agent_id="memory.chief",
        new_status=MemoryStatus.ACTIVE,
        reason="externally_revalidated",
        evidence_refs=("evidence-revalidated",),
        correction_ref="correction-revalidated",
    )
    return lifecycle, memory, registry, events


def _rehash_receipt(raw: dict[str, object]) -> None:
    payload = dict(raw)
    payload.pop("digest", None)
    raw["digest"] = canonical_digest(payload)


def test_lifecycle_restore_rejects_rehashed_broken_transition_continuity() -> None:
    lifecycle, memory, registry, events = _lifecycle_with_reactivation()
    state = lifecycle.to_state()
    second = state["receipts"][1]
    second["previous_status"] = MemoryStatus.QUARANTINED.value
    _rehash_receipt(second)

    with pytest.raises(ValueError, match="continuity"):
        MemoryLifecycleLedger.from_state(
            registry=registry,
            memory=memory,
            events=events,
            state=state,
        )


def test_lifecycle_restore_rejects_rehashed_receipt_sequence_gap() -> None:
    lifecycle, memory, registry, events = _lifecycle_with_reactivation()
    state = lifecycle.to_state()
    second = state["receipts"][1]
    second["receipt_id"] = "memory-lifecycle-00000003"
    _rehash_receipt(second)

    with pytest.raises(ValueError, match="sequence"):
        MemoryLifecycleLedger.from_state(
            registry=registry,
            memory=memory,
            events=events,
            state=state,
        )


def _verified_skill_engine() -> tuple[SkillEvolutionEngine, str]:
    evolution = SkillEvolutionEngine()
    skill = evolution.propose(
        owner_agent_id="memory.chief",
        region="memory-context-knowledge",
        name="governed-learning",
        body="persist only after causal and regression validation",
    )
    evolution.verify(
        skill.skill_id,
        EvidenceRecord(
            "evidence-external",
            "memory.worker",
            True,
            false_accepts=0,
            regressions=0,
        ),
    )
    return evolution, skill.skill_id


def _bare_individual_evolution(
    evolution: SkillEvolutionEngine,
    governed_skill_promoter=None,
) -> IndividualEvolutionControlPlane:
    plane = object.__new__(IndividualEvolutionControlPlane)
    plane.evolution = evolution
    plane.registry = _RegistryStub()
    plane.governed_skill_promoter = governed_skill_promoter
    plane._append_lineage = lambda *args, **kwargs: None
    return plane


def test_individual_evolution_cannot_bypass_governed_persistent_skill_promotion() -> None:
    evolution, skill_id = _verified_skill_engine()
    plane = _bare_individual_evolution(evolution)

    with pytest.raises(PermissionError, match="governed"):
        plane.promote_skill(skill_id, SkillScope.PERSONAL)

    assert evolution.get(skill_id).scope is SkillScope.CANDIDATE


def test_individual_evolution_delegates_persistent_skill_promotion_to_governed_port() -> None:
    evolution, skill_id = _verified_skill_engine()

    class _GovernedPromoter:
        def __init__(self, skills: SkillEvolutionEngine) -> None:
            self.skills = skills
            self.calls: list[tuple[str, SkillScope]] = []

        def promote_skill(self, requested_skill_id: str, scope: SkillScope):
            normalized = SkillScope(scope)
            self.calls.append((str(requested_skill_id), normalized))
            return self.skills.promote(requested_skill_id, normalized)

    promoter = _GovernedPromoter(evolution)
    plane = _bare_individual_evolution(evolution, promoter)
    promoted = plane.promote_skill(skill_id, SkillScope.PERSONAL)

    assert promoter.calls == [(skill_id, SkillScope.PERSONAL)]
    assert promoted.scope is SkillScope.PERSONAL
