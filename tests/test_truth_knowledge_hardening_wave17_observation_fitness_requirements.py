from __future__ import annotations

import pytest

from nolane.external_core.evidence_truth import EvidenceChannel
from nolane.external_core.knowledge_observation_truth import (
    ObservationRequirement,
    ObservationRequirementRegistry,
    ObservationRequirementSetRevision,
)
from nolane.external_core.knowledge_observation_fitness_truth import (
    OBSERVATION_FITNESS_REQUIREMENT_PROJECTION_PROTOCOL,
    ObservationFitnessRequirement,
    ObservationFitnessRequirementRegistry,
    ObservationFitnessRequirementSetRevision,
)
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger


def _knowledge() -> tuple[KnowledgeLedger, KnowledgeClaim, KnowledgeClaim]:
    ledger = KnowledgeLedger()
    target = ledger.add(
        KnowledgeClaim.create(
            claim_id="claim-target",
            subject="service",
            relation="healthy",
            object="yes",
        )
    )
    unrelated = ledger.add(
        KnowledgeClaim.create(
            claim_id="claim-unrelated",
            subject="other",
            relation="healthy",
            object="yes",
        )
    )
    return ledger, target, unrelated


def _observation_requirement(
    *,
    knowledge: KnowledgeLedger,
    claim: KnowledgeClaim,
    observation_id: str = "obs.case.001",
    channel: EvidenceChannel = EvidenceChannel.TEST,
) -> tuple[ObservationRequirementRegistry, ObservationRequirement]:
    registry = ObservationRequirementRegistry()
    requirement = ObservationRequirement.create(
        claim=claim,
        observation_id=observation_id,
        channel=channel,
    )
    registry.register(
        ObservationRequirementSetRevision.create(
            claim=claim,
            requirements=(requirement,),
        ),
        knowledge=knowledge,
    )
    return registry, requirement


def test_a17_fitness_requirement_is_exact_observation_snapshot_bound():
    knowledge, claim, _ = _knowledge()
    observation_registry, observation_requirement = _observation_requirement(
        knowledge=knowledge,
        claim=claim,
    )

    row = ObservationFitnessRequirement.create(
        claim=claim,
        observation_requirement=observation_requirement,
    )
    same = ObservationFitnessRequirement.create(
        claim=claim,
        observation_requirement=observation_requirement,
    )

    assert row == same
    assert row.claim_id == claim.claim_id
    assert row.claim_content_digest == claim.content_digest
    assert row.observation_id == observation_requirement.observation_id
    assert row.observation_requirement_digest == observation_requirement.digest
    assert row.channel is observation_requirement.channel

    other_requirement = ObservationRequirement.create(
        claim=claim,
        observation_id="obs.case.002",
        channel=EvidenceChannel.AUDIT,
    )
    with pytest.raises(ValueError, match="current required observation"):
        ObservationFitnessRequirementRegistry().register(
            ObservationFitnessRequirementSetRevision.create(
                claim=claim,
                requirements=(
                    ObservationFitnessRequirement.create(
                        claim=claim,
                        observation_requirement=other_requirement,
                    ),
                ),
            ),
            knowledge=knowledge,
            observation_requirements=observation_registry,
        )


def test_a17_fitness_requirement_registry_is_append_only_and_relevant_only():
    knowledge, claim, unrelated = _knowledge()
    observation_registry, observation_requirement = _observation_requirement(
        knowledge=knowledge,
        claim=claim,
    )
    unrelated_observation_registry, unrelated_requirement = _observation_requirement(
        knowledge=knowledge,
        claim=unrelated,
        observation_id="obs.other.001",
        channel=EvidenceChannel.AUDIT,
    )

    registry = ObservationFitnessRequirementRegistry()
    before = registry.projection_digest((claim.claim_id,))
    assert registry.projection_state((claim.claim_id,))["claims"] == [
        {"claim_id": claim.claim_id, "status": "unconstrained"}
    ]

    unrelated_row = ObservationFitnessRequirement.create(
        claim=unrelated,
        observation_requirement=unrelated_requirement,
    )
    registry.register(
        ObservationFitnessRequirementSetRevision.create(
            claim=unrelated,
            requirements=(unrelated_row,),
        ),
        knowledge=knowledge,
        observation_requirements=unrelated_observation_registry,
    )
    assert registry.projection_digest((claim.claim_id,)) == before

    target_row = ObservationFitnessRequirement.create(
        claim=claim,
        observation_requirement=observation_requirement,
    )
    first = registry.register(
        ObservationFitnessRequirementSetRevision.create(
            claim=claim,
            requirements=(target_row,),
        ),
        knowledge=knowledge,
        observation_requirements=observation_registry,
    )
    projection = registry.projection_state((claim.claim_id,))
    assert projection["protocol"] == OBSERVATION_FITNESS_REQUIREMENT_PROJECTION_PROTOCOL
    assert projection["claims"][0]["status"] == "fitness-required"
    assert projection["claims"][0]["revision_digest"] == first.digest

    with pytest.raises(ValueError, match="advance exactly once"):
        registry.register(
            ObservationFitnessRequirementSetRevision.create(
                claim=claim,
                revision=3,
                predecessor_digest=first.digest,
                requirements=(target_row,),
            ),
            knowledge=knowledge,
            observation_requirements=observation_registry,
        )


def test_a17_fitness_requirement_restore_rejects_protocol_tamper_and_snapshot_drift():
    knowledge, claim, _ = _knowledge()
    observation_registry, observation_requirement = _observation_requirement(
        knowledge=knowledge,
        claim=claim,
    )
    registry = ObservationFitnessRequirementRegistry()
    row = ObservationFitnessRequirement.create(
        claim=claim,
        observation_requirement=observation_requirement,
    )
    registry.register(
        ObservationFitnessRequirementSetRevision.create(
            claim=claim,
            requirements=(row,),
        ),
        knowledge=knowledge,
        observation_requirements=observation_registry,
    )

    state = registry.to_state()
    assert ObservationFitnessRequirementRegistry.from_state(
        state,
        knowledge=knowledge,
        observation_requirements=observation_registry,
    ).to_state() == state

    wrong_protocol = dict(state)
    wrong_protocol["protocol"] = "wrong"
    with pytest.raises(ValueError, match="protocol"):
        ObservationFitnessRequirementRegistry.from_state(
            wrong_protocol,
            knowledge=knowledge,
            observation_requirements=observation_registry,
        )

    tampered = dict(state)
    revision = dict(state["revisions"][0])
    requirement = dict(revision["requirements"][0])
    requirement["observation_requirement_digest"] = "tampered"
    revision["requirements"] = [requirement]
    tampered["revisions"] = [revision]
    with pytest.raises(ValueError, match="snapshot"):
        ObservationFitnessRequirementRegistry.from_state(
            tampered,
            knowledge=knowledge,
            observation_requirements=observation_registry,
        )
