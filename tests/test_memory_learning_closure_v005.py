from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.individual_evolution import EvolutionLineageEntry, IndividualEvolutionControlPlane
from nolane.external_core.self_model import SelfModelRegistry
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


class _SelfModelRegistryStub(_RegistryStub):
    def __init__(self) -> None:
        super().__init__()
        self._actors["memory.chief"].self_model_version = "self-model-0.1"
        self._actors["memory.worker"].self_model_version = "self-model-0.1"

    def identities(self):
        return tuple(self._actors[key] for key in sorted(self._actors))

    def set_self_model_version(self, agent_id: str, version: str) -> None:
        self.get(agent_id).self_model_version = str(version)


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


def test_self_model_restore_rejects_revision_rollback_against_committed_version() -> None:
    registry = _SelfModelRegistryStub()
    state = SelfModelRegistry(registry).to_state()
    chief = next(row for row in state["models"] if row["agent_id"] == "memory.chief")
    chief["version"] = "self-model-00000005"
    state["revisions"]["memory.chief"] = 1

    with pytest.raises(ValueError, match="revision"):
        SelfModelRegistry.from_state(registry, state)


def test_self_model_restore_rejects_duplicate_agent_rows() -> None:
    registry = _SelfModelRegistryStub()
    state = SelfModelRegistry(registry).to_state()
    chief = next(row for row in state["models"] if row["agent_id"] == "memory.chief")
    state["models"].append(dict(chief))

    with pytest.raises(ValueError, match="duplicate"):
        SelfModelRegistry.from_state(registry, state)


def test_individual_evolution_state_preserves_global_lineage_sequence() -> None:
    first = EvolutionLineageEntry(
        sequence=1,
        entry_id="lineage-first",
        agent_id="z.agent",
        transition="first",
        neural_version="n1",
        self_model_version="s1",
        specialization_signature="sig-z",
    )
    second = EvolutionLineageEntry(
        sequence=2,
        entry_id="lineage-second",
        agent_id="a.agent",
        transition="second",
        neural_version="n2",
        self_model_version="s2",
        specialization_signature="sig-a",
    )

    class _StateStub:
        def to_state(self):
            return {}

    plane = object.__new__(IndividualEvolutionControlPlane)
    plane.profiles = _StateStub()
    plane.experiences = _StateStub()
    plane._lineage = {"z.agent": [first], "a.agent": [second]}
    plane._observations = {}
    plane._lineage_counter = 2

    state = plane.to_state()
    assert [row["sequence"] for row in state["lineage"]] == [1, 2]
