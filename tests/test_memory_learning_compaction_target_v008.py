from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.core.canonical_digest import canonical_digest
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


def _compacted_substrate():
    from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    first = substrate.remember(
        text="verified source alpha",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("source-alpha-proof",),
        source_refs=("source-alpha",),
    )
    second = substrate.remember(
        text="verified source beta",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("source-beta-proof",),
        source_refs=("source-beta",),
    )
    compacted, receipt = substrate.compact(
        source_memory_ids=(first.memory_id, second.memory_id),
        summary_text="alpha and beta are jointly verified",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        actor_agent_id="memory.worker",
        evidence_refs=("external-compaction-review",),
    )
    return substrate, compacted, receipt


def test_restore_rejects_compacted_target_text_tampering() -> None:
    from nolane.memory.learning_substrate import LearningSubstrate

    substrate, compacted, _ = _compacted_substrate()
    state = substrate.to_state()
    target = next(
        row for row in state["memory"]["entries"] if row["memory_id"] == compacted.memory_id
    )
    target["text"] = "forged summary that was never reviewed"

    with pytest.raises(ValueError, match="compacted target digest"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_restore_rejects_legacy_compaction_receipt_without_target_digest() -> None:
    from nolane.memory.learning_substrate import LearningSubstrate

    substrate, _, _ = _compacted_substrate()
    state = substrate.to_state()
    raw = dict(state["compactions"][0])
    raw.pop("compacted_digest", None)
    raw["schema"] = "nolane-memory-compaction-receipt-v1"
    identity = {
        "schema": "nolane-memory-compaction-receipt-v1",
        "source_memory_ids": list(raw["source_memory_ids"]),
        "compacted_memory_id": raw["compacted_memory_id"],
        "source_digest": raw["source_digest"],
        "epistemic_type": raw["epistemic_type"],
        "actor_agent_id": raw["actor_agent_id"],
        "evidence_refs": list(raw["evidence_refs"]),
    }
    raw["compaction_id"] = "mcr-" + canonical_digest(identity)[:24]
    state["compactions"][0] = raw

    with pytest.raises(ValueError, match="compaction receipt requires v2 target digest"):
        LearningSubstrate.from_state(registry=_RegistryStub(), events=_EventStub(), state=state)


def test_compaction_target_digest_ignores_later_lifecycle_status_changes() -> None:
    from nolane.memory.learning_substrate import LearningSubstrate

    substrate, compacted, receipt = _compacted_substrate()
    substrate.decay_memory(
        compacted.memory_id,
        actor_agent_id="memory.worker",
        reason="freshness window elapsed",
        evidence_refs=("freshness-observation",),
    )
    state = substrate.to_state()

    restored = LearningSubstrate.from_state(
        registry=_RegistryStub(),
        events=_EventStub(),
        state=state,
    )

    assert restored.memory.get(compacted.memory_id).status is MemoryStatus.STALE
    assert tuple(row.memory_id for row in restored.reconstruct_compaction(receipt.compaction_id)) == receipt.source_memory_ids


def test_compaction_target_integrity_advances_lifecycle_authority_revision() -> None:
    from cogcoder.refoundation.component_versions import component_version
    from nolane.memory import lifecycle

    assert lifecycle.COMPONENT_ID == "external.memory.lifecycle"
    assert lifecycle.COMPONENT_VERSION == "0.0.6"
    assert str(component_version("external.memory.lifecycle")) == "0.0.6"
