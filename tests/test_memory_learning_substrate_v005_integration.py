from __future__ import annotations

from types import SimpleNamespace

import pytest

from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.self_model import SelfModelRegistry
from nolane.memory.experience import ExperienceLedger, ExperienceOutcome, LearningLayer
from nolane.memory.fabric import MemoryScope, MemoryStatus
from nolane.memory.learning_substrate import EpistemicType, LearningSubstrate, MemoryKind
from tests.memory_learning_authority_helpers import admit_memory


class _Registry:
    def __init__(self) -> None:
        self._actors = {
            "memory.chief": SimpleNamespace(
                agent_id="memory.chief", region="memory-context-knowledge", self_model_version="self-model-0.1"
            ),
            "memory.worker": SimpleNamespace(
                agent_id="memory.worker", region="memory-context-knowledge", self_model_version="self-model-0.1"
            ),
        }

    def get(self, agent_id: str):
        return self._actors[str(agent_id)]

    def identities(self):
        return tuple(self._actors.values())

    def set_self_model_version(self, agent_id: str, version: str):
        self._actors[str(agent_id)].self_model_version = str(version)
        return self._actors[str(agent_id)]


class _Events:
    def latest_event_id(self):
        return None

    def get(self, event_id: str):
        raise KeyError(event_id)


def test_failure_experience_is_preserved_as_quarantined_failure_memory() -> None:
    registry, events = _Registry(), _Events()
    experiences = ExperienceLedger(registry=registry, events=events)
    experience = experiences.record(
        agent_id="memory.chief",
        author_agent_id="memory.chief",
        domain="api-migration",
        outcome=ExperienceOutcome.FAILURE,
        summary="legacy_id lookup failed under API v4",
        evidence_refs=("log-run-7",),
    )
    substrate = LearningSubstrate(registry=registry, events=events, experiences=experiences)
    memory = substrate.remember_experience(
        experience.experience_id,
        failure_condition="API major version is 4 and legacy_id is requested",
        retry_if_changed="retry only if the API contract or major version changes",
    )
    metadata = substrate.metadata(memory.memory_id)
    assert memory.status is MemoryStatus.QUARANTINED
    assert metadata.kind is MemoryKind.FAILURE
    assert metadata.epistemic_type is EpistemicType.OBSERVATION
    assert experience.experience_id in metadata.source_refs


def test_clean_external_attribution_consolidates_into_verified_active_memory() -> None:
    registry, events = _Registry(), _Events()
    experiences = ExperienceLedger(registry=registry, events=events)
    experience = experiences.record(
        agent_id="memory.chief",
        author_agent_id="memory.chief",
        domain="retrieval",
        outcome=ExperienceOutcome.SUCCESS,
        summary="revalidation prevented stale anchor reuse",
    )
    attribution = experiences.attribute(
        experience.experience_id,
        learning_layer=LearningLayer.PROCEDURAL,
        lesson="revalidate a versioned anchor before reuse",
        evidence=EvidenceRecord("evidence-external", "memory.worker", True),
    )
    substrate = LearningSubstrate(registry=registry, events=events, experiences=experiences)
    memory = substrate.consolidate_attribution(attribution.attribution_id)
    memory = admit_memory(substrate, memory, evidence_id="evidence-external-admission")
    metadata = substrate.metadata(memory.memory_id)
    assert memory.status is MemoryStatus.ACTIVE
    assert metadata.epistemic_type is EpistemicType.VERIFIED
    assert metadata.kind is MemoryKind.PROCEDURAL
    assert attribution.attribution_id in metadata.source_refs


def test_lifecycle_validation_and_decay_are_evidence_bounded() -> None:
    registry, events = _Registry(), _Events()
    substrate = LearningSubstrate(registry=registry, events=events)
    memory = substrate.remember(
        text="candidate observation",
        owner_agent_id="memory.chief",
        scope=MemoryScope.PERSONAL,
        kind=MemoryKind.SEMANTIC,
        epistemic_type=EpistemicType.OBSERVATION,
    )
    with pytest.raises(PermissionError):
        substrate.validate_memory(
            memory.memory_id,
            actor_agent_id="memory.worker",
            evidence_refs=("evidence-1",),
            correction_ref="verification://1",
        )
    active = admit_memory(substrate, memory, evidence_id="evidence-1")
    assert active.status is MemoryStatus.ACTIVE
    stale = substrate.decay_memory(
        memory.memory_id,
        actor_agent_id="memory.worker",
        reason="validity_window_expired",
        evidence_refs=("clock-evidence",),
    )
    assert stale.status is MemoryStatus.STALE


def test_self_model_records_failure_blind_spot_and_calibration_without_self_authority() -> None:
    registry = _Registry()
    models = SelfModelRegistry(registry)
    external = EvidenceRecord("evidence-model", "memory.worker", True)
    model = models.record_failure_mode(
        "memory.chief", failure_mode="over-trusts stale anchors", evidence=external
    )
    model = models.record_blind_spot(
        "memory.chief", blind_spot="version drift without source receipt", evidence=external
    )
    model = models.update_calibration("memory.chief", calibration=0.74, evidence=external)
    assert "over-trusts stale anchors" in model.failure_modes
    assert "version drift without source receipt" in model.blind_spots
    assert model.calibration == pytest.approx(0.74)
    with pytest.raises(PermissionError, match="external"):
        models.record_failure_mode(
            "memory.chief",
            failure_mode="self-certified failure",
            evidence=EvidenceRecord("evidence-self", "memory.chief", True),
        )
