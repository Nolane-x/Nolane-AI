from __future__ import annotations

import pytest

from nolane.external_core.evidence_truth import EvidenceChannel
from nolane.external_core.knowledge_observation_truth import (
    OBSERVATION_REQUIREMENT_PROJECTION_PROTOCOL,
    OBSERVATION_REQUIREMENT_PROTOCOL,
    ObservationRequirement,
    ObservationRequirementRegistry,
    ObservationRequirementSetRevision,
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


def test_a16_observation_requirement_is_canonical_and_exact_claim_bound():
    _, claim, _ = _knowledge()
    first = ObservationRequirement.create(
        claim=claim,
        observation_id="obs.case.002",
        channel=EvidenceChannel.TEST,
    )
    same = ObservationRequirement.create(
        claim=claim,
        observation_id="obs.case.002",
        channel=EvidenceChannel.TEST,
    )
    assert first == same
    assert first.claim_id == claim.claim_id
    assert first.claim_content_digest == claim.content_digest
    assert first.channel is EvidenceChannel.TEST

    with pytest.raises(ValueError, match="explicit"):
        ObservationRequirement.create(
            claim=claim,
            observation_id="",
            channel=EvidenceChannel.TEST,
        )


def test_a16_requirement_registry_sorts_requirements_and_rejects_duplicate_observation_ids():
    knowledge, claim, _ = _knowledge()
    registry = ObservationRequirementRegistry()
    second = ObservationRequirement.create(
        claim=claim,
        observation_id="obs.case.002",
        channel=EvidenceChannel.TEST,
    )
    first = ObservationRequirement.create(
        claim=claim,
        observation_id="obs.case.001",
        channel=EvidenceChannel.OBSERVATION,
    )
    revision = registry.register(
        ObservationRequirementSetRevision.create(
            claim=claim,
            requirements=(second, first),
        ),
        knowledge=knowledge,
    )
    assert tuple(row.observation_id for row in revision.requirements) == (
        "obs.case.001",
        "obs.case.002",
    )
    assert registry.requirements(claim.claim_id) == revision.requirements

    duplicate = ObservationRequirement.create(
        claim=claim,
        observation_id="obs.case.001",
        channel=EvidenceChannel.AUDIT,
    )
    with pytest.raises(ValueError, match="observation ids must be unique"):
        ObservationRequirementSetRevision.create(
            claim=claim,
            requirements=(first, duplicate),
        )


def test_a16_requirement_registry_enforces_strict_revision_and_predecessor_chain():
    knowledge, claim, _ = _knowledge()
    registry = ObservationRequirementRegistry()
    first_req = ObservationRequirement.create(
        claim=claim,
        observation_id="obs.case.001",
        channel=EvidenceChannel.TEST,
    )
    first = registry.register(
        ObservationRequirementSetRevision.create(
            claim=claim,
            revision=1,
            requirements=(first_req,),
        ),
        knowledge=knowledge,
    )

    with pytest.raises(ValueError, match="advance exactly once"):
        registry.register(
            ObservationRequirementSetRevision.create(
                claim=claim,
                revision=3,
                predecessor_digest=first.digest,
                requirements=(first_req,),
            ),
            knowledge=knowledge,
        )

    with pytest.raises(ValueError, match="predecessor"):
        registry.register(
            ObservationRequirementSetRevision.create(
                claim=claim,
                revision=2,
                predecessor_digest="wrong",
                requirements=(first_req,),
            ),
            knowledge=knowledge,
        )

    second_req = ObservationRequirement.create(
        claim=claim,
        observation_id="obs.case.002",
        channel=EvidenceChannel.AUDIT,
    )
    second = registry.register(
        ObservationRequirementSetRevision.create(
            claim=claim,
            revision=2,
            predecessor_digest=first.digest,
            requirements=(first_req, second_req),
        ),
        knowledge=knowledge,
    )
    assert registry.current(claim.claim_id) == second


def test_a16_requirement_projection_marks_unconstrained_and_is_relevant_only():
    knowledge, claim, unrelated = _knowledge()
    registry = ObservationRequirementRegistry()
    state = registry.projection_state((claim.claim_id,))
    assert state["protocol"] == OBSERVATION_REQUIREMENT_PROJECTION_PROTOCOL
    assert state["claims"] == [
        {"claim_id": claim.claim_id, "status": "unconstrained"}
    ]
    before = registry.projection_digest((claim.claim_id,))

    unrelated_req = ObservationRequirement.create(
        claim=unrelated,
        observation_id="obs.other.001",
        channel=EvidenceChannel.TEST,
    )
    registry.register(
        ObservationRequirementSetRevision.create(
            claim=unrelated,
            requirements=(unrelated_req,),
        ),
        knowledge=knowledge,
    )
    assert registry.projection_digest((claim.claim_id,)) == before

    target_req = ObservationRequirement.create(
        claim=claim,
        observation_id="obs.target.001",
        channel=EvidenceChannel.TEST,
    )
    registry.register(
        ObservationRequirementSetRevision.create(
            claim=claim,
            requirements=(target_req,),
        ),
        knowledge=knowledge,
    )
    assert registry.projection_digest((claim.claim_id,)) != before


def test_a16_requirement_registry_restore_rejects_tamper_duplicates_and_unexpected_fields():
    knowledge, claim, _ = _knowledge()
    registry = ObservationRequirementRegistry()
    req = ObservationRequirement.create(
        claim=claim,
        observation_id="obs.target.001",
        channel=EvidenceChannel.TEST,
    )
    registry.register(
        ObservationRequirementSetRevision.create(
            claim=claim,
            requirements=(req,),
        ),
        knowledge=knowledge,
    )
    state = registry.to_state()
    assert state["protocol"] == OBSERVATION_REQUIREMENT_PROTOCOL
    assert ObservationRequirementRegistry.from_state(
        state,
        knowledge=knowledge,
    ).to_state() == state

    wrong_protocol = dict(state)
    wrong_protocol["protocol"] = "wrong"
    with pytest.raises(ValueError, match="protocol"):
        ObservationRequirementRegistry.from_state(
            wrong_protocol,
            knowledge=knowledge,
        )

    unexpected = dict(state)
    unexpected["extra"] = True
    with pytest.raises(ValueError, match="unexpected"):
        ObservationRequirementRegistry.from_state(
            unexpected,
            knowledge=knowledge,
        )

    duplicate = dict(state)
    duplicate["revisions"] = [state["revisions"][0], state["revisions"][0]]
    with pytest.raises(ValueError, match="duplicate"):
        ObservationRequirementRegistry.from_state(
            duplicate,
            knowledge=knowledge,
        )

    tampered = dict(state)
    revision_state = dict(state["revisions"][0])
    requirement_state = dict(revision_state["requirements"][0])
    requirement_state["claim_content_digest"] = "tampered"
    revision_state["requirements"] = [requirement_state]
    tampered["revisions"] = [revision_state]
    with pytest.raises(ValueError, match="content digest"):
        ObservationRequirementRegistry.from_state(
            tampered,
            knowledge=knowledge,
        )
