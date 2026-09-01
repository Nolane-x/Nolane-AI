from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.fabric import MemoryScope
from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind


class _RegistryStub:
    def __init__(self) -> None:
        self._actors = {
            "memory.chief": SimpleNamespace(agent_id="memory.chief", region="memory-context-knowledge"),
            "memory.worker": SimpleNamespace(agent_id="memory.worker", region="memory-context-knowledge"),
            "verification.chief": SimpleNamespace(agent_id="verification.chief", region="truth-knowledge"),
        }

    def get(self, agent_id: str):
        return self._actors[str(agent_id)]


class _EventStub:
    def latest_event_id(self):
        return None

    def get(self, event_id: str):
        raise KeyError(event_id)


def test_rejected_non_chief_activation_does_not_consume_verification_lease() -> None:
    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    row = substrate.remember(
        text="candidate requiring governed admission",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.VERIFIED,
        evidence_ids=("caller-string-is-not-authority",),
    )
    evidence = EvidenceRecord(
        "transaction-proof",
        "verification.chief",
        True,
        false_accepts=0,
        regressions=0,
    )
    digest = substrate.memory_verification_subject_digest(
        row.memory_id,
        actor_agent_id="memory.worker",
    )
    lease = substrate.learning_authority.issue(
        subject_kind="memory",
        subject_id=row.memory_id,
        operation_class="memory.verify",
        producer_agent_id=row.owner_agent_id,
        evidence=evidence,
        subject_digest=digest,
        single_use=True,
    )

    with pytest.raises(PermissionError, match="Memory Chief"):
        substrate.validate_memory(
            row.memory_id,
            actor_agent_id="memory.worker",
            evidence=evidence,
            authority_lease_id=lease.lease_id,
        )

    assert substrate.learning_authority.uses_for(lease.lease_id) == ()
