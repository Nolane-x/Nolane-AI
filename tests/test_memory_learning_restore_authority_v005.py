from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.experience import ExperienceLedger
from nolane.memory.fabric import MemoryFabric, MemoryScope, MemoryStatus
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


def _experience_id_for_state(raw: dict[str, object]) -> str:
    payload = {
        "agent_id": raw["agent_id"],
        "region": raw["region"],
        "domain": raw["domain"],
        "outcome": raw["outcome"],
        "summary": raw["summary"],
        "task_id": raw.get("task_id"),
        "object_refs": list(raw.get("object_refs", ())),
        "evidence_refs": list(raw.get("evidence_refs", ())),
    }
    return "experience-" + canonical_digest(payload)[:24]


def _attribution_id_for_state(raw: dict[str, object]) -> str:
    payload = {
        "experience_id": raw["experience_id"],
        "agent_id": raw["agent_id"],
        "learning_layer": raw["learning_layer"],
        "lesson": raw["lesson"],
        "positive": raw["positive"],
        "verifier_agent_id": raw["verifier_agent_id"],
        "evidence": dict(raw["evidence"]),
    }
    return "attribution-" + canonical_digest(payload)[:24]


def _experience_ledger_with_positive_attribution():
    from nolane.memory.experience import ExperienceLedger

    registry = _RegistryStub()
    events = _EventStub()
    ledger = ExperienceLedger(registry=registry, events=events)
    experience = ledger.record(
        agent_id="memory.chief",
        author_agent_id="memory.chief",
        domain="memory-governance",
        outcome="success",
        summary="restore authority remains fail closed",
        task_id="memory-b-closure",
        object_refs=("nolane/memory/experience.py",),
        evidence_refs=("experience-evidence",),
    )
    attribution = ledger.attribute(
        experience.experience_id,
        learning_layer="procedural",
        lesson="replay canonical authority on restore",
        evidence=EvidenceRecord(
            "attribution-evidence",
            "memory.worker",
            True,
            false_accepts=0,
            regressions=0,
        ),
    )
    return ledger, registry, events, experience, attribution


def test_experience_restore_rejects_content_address_rebinding() -> None:
    from nolane.memory.experience import ExperienceLedger

    ledger, registry, events, _, _ = _experience_ledger_with_positive_attribution()
    state = ledger.to_state()
    state["experiences"][0]["summary"] = "tampered summary under old content address"

    with pytest.raises(ValueError, match="experience.*id|canonical"):
        ExperienceLedger.from_state(registry=registry, events=events, state=state)


def test_experience_restore_rejects_rehashed_identity_region_rebinding() -> None:
    from nolane.memory.experience import ExperienceLedger

    ledger, registry, events, _, _ = _experience_ledger_with_positive_attribution()
    state = ledger.to_state()
    raw = state["experiences"][0]
    raw["region"] = "forged-region"
    raw["experience_id"] = _experience_id_for_state(raw)
    state["attributions"] = []

    with pytest.raises(ValueError, match="region|canonical|experience.*id"):
        ExperienceLedger.from_state(registry=registry, events=events, state=state)


def test_experience_restore_rejects_rehashed_self_certified_positive_attribution() -> None:
    from nolane.memory.experience import ExperienceLedger

    ledger, registry, events, _, _ = _experience_ledger_with_positive_attribution()
    state = ledger.to_state()
    raw = state["attributions"][0]
    raw["verifier_agent_id"] = "memory.chief"
    raw["evidence"]["verifier_agent_id"] = "memory.chief"
    raw["positive"] = True
    raw["attribution_id"] = _attribution_id_for_state(raw)

    with pytest.raises(PermissionError, match="external"):
        ExperienceLedger.from_state(registry=registry, events=events, state=state)


def test_experience_restore_rejects_duplicate_serialized_rows() -> None:
    from nolane.memory.experience import ExperienceLedger

    ledger, registry, events, _, _ = _experience_ledger_with_positive_attribution()
    state = ledger.to_state()
    state["experiences"].append(dict(state["experiences"][0]))

    with pytest.raises(ValueError, match="duplicate.*experience"):
        ExperienceLedger.from_state(registry=registry, events=events, state=state)


def _skill_engine_with_external_evidence() -> tuple[SkillEvolutionEngine, str]:
    engine = SkillEvolutionEngine()
    skill = engine.propose(
        owner_agent_id="memory.chief",
        region="memory-context-knowledge",
        name="restore-authority",
        body="persist only canonical governed skill state",
    )
    engine.verify(
        skill.skill_id,
        EvidenceRecord(
            "skill-evidence-1",
            "memory.worker",
            True,
            false_accepts=0,
            regressions=0,
        ),
    )
    return engine, skill.skill_id


def test_skill_restore_rejects_content_address_rebinding() -> None:
    engine, _ = _skill_engine_with_external_evidence()
    state = engine.to_state()
    state["skills"][0]["body"] = "tampered body under old digest"

    with pytest.raises(ValueError, match="skill.*digest|skill.*id|canonical"):
        SkillEvolutionEngine.from_state(state)


def test_skill_restore_rejects_scope_without_required_verifier_quorum() -> None:
    engine = SkillEvolutionEngine()
    engine.propose(
        owner_agent_id="memory.chief",
        region="memory-context-knowledge",
        name="unverified-global",
        body="must not become globally authoritative without quorum",
    )
    state = engine.to_state()
    state["skills"][0]["scope"] = SkillScope.GLOBAL.value

    with pytest.raises(PermissionError, match="global promotion requires 3 independent valid verifier"):
        SkillEvolutionEngine.from_state(state)


def test_skill_restore_rejects_duplicate_evidence_ids() -> None:
    engine, _ = _skill_engine_with_external_evidence()
    state = engine.to_state()
    state["skills"][0]["evidence"].append(dict(state["skills"][0]["evidence"][0]))

    with pytest.raises(ValueError, match="duplicate.*evidence"):
        SkillEvolutionEngine.from_state(state)


def test_skill_restore_rejects_quarantine_reason_inconsistency() -> None:
    engine, _ = _skill_engine_with_external_evidence()
    state = engine.to_state()
    state["skills"][0]["quarantine_reason"] = "forged quarantine history"

    with pytest.raises(ValueError, match="quarantine"):
        SkillEvolutionEngine.from_state(state)


def _fabric_state() -> dict[str, object]:
    memory = MemoryFabric()
    first = memory.write(
        MemoryScope.PERSONAL,
        "canonical first memory",
        owner_agent_id="memory.chief",
        tags=("a", "b"),
        evidence_ids=("evidence-a", "evidence-b"),
        dependencies=("dep-a", "dep-b"),
    )
    memory.write(
        MemoryScope.PERSONAL,
        "canonical second memory",
        owner_agent_id="memory.chief",
        supersedes=first.memory_id,
    )
    return memory.to_state()


def test_memory_fabric_restore_rejects_empty_write_fields() -> None:
    state = _fabric_state()
    state["entries"][0]["text"] = "   "

    with pytest.raises(ValueError, match="memory text must be non-empty"):
        MemoryFabric.from_state(state)


def test_memory_fabric_restore_rejects_missing_scope_binding() -> None:
    state = _fabric_state()
    state["entries"][0]["scope"] = MemoryScope.REGION.value
    state["entries"][0]["region"] = None

    with pytest.raises(ValueError, match="regional memory requires a region"):
        MemoryFabric.from_state(state)


def test_memory_fabric_restore_rejects_inactive_state_without_reason() -> None:
    state = _fabric_state()
    state["entries"][1]["status"] = MemoryStatus.ARCHIVED.value
    state["entries"][1]["status_reason"] = None

    with pytest.raises(ValueError, match="inactive memory state requires a reason"):
        MemoryFabric.from_state(state)


def test_memory_fabric_restore_rejects_active_state_with_stale_reason() -> None:
    state = _fabric_state()
    state["entries"][1]["status"] = MemoryStatus.ACTIVE.value
    state["entries"][1]["status_reason"] = "forged inactive history"

    with pytest.raises(ValueError, match="active.*reason|canonical"):
        MemoryFabric.from_state(state)


def test_memory_fabric_restore_rejects_noncanonical_normalized_collections() -> None:
    state = _fabric_state()
    state["entries"][0]["tags"] = ["b", "a", "b"]

    with pytest.raises(ValueError, match="tags|canonical"):
        MemoryFabric.from_state(state)


def test_memory_fabric_restore_rejects_forward_supersedes_reference() -> None:
    memory = MemoryFabric()
    memory.write(MemoryScope.PERSONAL, "first", owner_agent_id="memory.chief")
    memory.write(MemoryScope.PERSONAL, "second", owner_agent_id="memory.chief")
    state = memory.to_state()
    state["entries"][0]["supersedes"] = "mem-00000002"

    with pytest.raises(ValueError, match="supersedes|earlier"):
        MemoryFabric.from_state(state)


def test_experience_restore_rejects_duplicate_attribution_rows() -> None:
    ledger, registry, events, _, _ = _experience_ledger_with_positive_attribution()
    state = ledger.to_state()
    state["attributions"].append(dict(state["attributions"][0]))

    with pytest.raises(ValueError, match="duplicate.*attribution"):
        ExperienceLedger.from_state(registry=registry, events=events, state=state)


def test_skill_restore_rejects_duplicate_skill_rows() -> None:
    engine, _ = _skill_engine_with_external_evidence()
    state = engine.to_state()
    state["skills"].append(dict(state["skills"][0]))

    with pytest.raises(ValueError, match="duplicate.*skill"):
        SkillEvolutionEngine.from_state(state)


def test_memory_fabric_restore_rejects_empty_owner() -> None:
    state = _fabric_state()
    state["entries"][0]["owner_agent_id"] = " "

    with pytest.raises(ValueError, match="memory owner must be explicit"):
        MemoryFabric.from_state(state)


def test_memory_fabric_restore_rejects_task_scope_without_task_id() -> None:
    state = _fabric_state()
    state["entries"][0]["scope"] = MemoryScope.TASK.value
    state["entries"][0]["task_id"] = None

    with pytest.raises(ValueError, match="task memory requires a task id"):
        MemoryFabric.from_state(state)


@pytest.mark.parametrize("field", ("tags", "evidence_ids", "dependencies"))
def test_memory_fabric_restore_rejects_noncanonical_set_like_fields(field: str) -> None:
    state = _fabric_state()
    state["entries"][0][field] = ["z", "a", "z"]

    with pytest.raises(ValueError, match=f"{field}|canonical"):
        MemoryFabric.from_state(state)
