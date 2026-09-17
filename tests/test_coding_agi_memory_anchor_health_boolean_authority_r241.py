from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.memory.fabric import MemoryScope
from tests.memory_learning_authority_helpers import authority_copy, remember_verified


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


def _substrate_with_verified_anchor():
    from nolane.memory.learning_substrate import LearningSubstrate, MemoryKind

    substrate = LearningSubstrate(registry=_RegistryStub(), events=_EventStub())
    anchor = remember_verified(
        substrate,
        evidence_id="r241-anchor-evidence",
        text="R2.41 exact boolean anchor",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.PROJECT_STATE,
    )
    return substrate, anchor


@pytest.mark.parametrize("alias", ["false", "true", 0, 1])
def test_record_anchor_health_rejects_non_boolean_aliases(alias: object) -> None:
    substrate, anchor = _substrate_with_verified_anchor()

    with pytest.raises(ValueError, match="healthy.*exact bool"):
        substrate.record_anchor_health(
            anchor.memory_id,
            actor_agent_id="memory.worker",
            healthy=alias,
            evidence_ref="r241-health-observation",
            observed_version_scope=None,
            reason="runtime observation must preserve exact boolean authority",
        )


def test_anchor_health_receipt_restore_rejects_truthy_false_alias() -> None:
    from nolane.memory.adaptive_policy import MemoryAnchorHealthReceipt

    substrate, anchor = _substrate_with_verified_anchor()
    receipt = substrate.record_anchor_health(
        anchor.memory_id,
        actor_agent_id="memory.worker",
        healthy=True,
        evidence_ref="r241-health-observation",
        observed_version_scope=None,
        reason="canonical healthy observation",
    )
    state = receipt.to_state()
    state["healthy"] = "false"

    with pytest.raises(ValueError, match="healthy.*exact bool"):
        MemoryAnchorHealthReceipt.from_state(state)


def test_learning_substrate_restore_rejects_truthy_false_anchor_health_alias() -> None:
    from nolane.memory.learning_substrate import LearningSubstrate

    substrate, anchor = _substrate_with_verified_anchor()
    substrate.record_anchor_health(
        anchor.memory_id,
        actor_agent_id="memory.worker",
        healthy=True,
        evidence_ref="r241-health-observation",
        observed_version_scope=None,
        reason="canonical healthy observation",
    )
    state = substrate.to_state()
    state["anchor_health"][0]["healthy"] = "false"

    with pytest.raises(ValueError, match="healthy.*exact bool"):
        LearningSubstrate.from_state(
            registry=_RegistryStub(),
            events=_EventStub(),
            state=state,
            learning_authority=authority_copy(substrate),
        )
