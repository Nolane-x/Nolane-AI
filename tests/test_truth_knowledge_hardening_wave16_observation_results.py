from __future__ import annotations

import pytest

from nolane.external_core.evidence_observation_truth import (
    OBSERVATION_RESULT_PROJECTION_PROTOCOL,
    OBSERVATION_RESULT_PROTOCOL,
    ObservationOutcome,
    ObservationResultLedger,
    ObservationResultRevision,
)
from nolane.external_core.evidence_truth import (
    EvidenceChannel,
    EvidenceLedger,
    EvidencePolarity,
    TruthEvidence,
)
from nolane.external_core.knowledge_observation_truth import ObservationRequirement
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


def _requirement(claim: KnowledgeClaim, observation_id: str = "obs.target.001") -> ObservationRequirement:
    return ObservationRequirement.create(
        claim=claim,
        observation_id=observation_id,
        channel=EvidenceChannel.TEST,
    )


def _evidence(
    ledger: EvidenceLedger,
    *,
    evidence_id: str,
    claim_id: str,
    channel: EvidenceChannel = EvidenceChannel.TEST,
) -> TruthEvidence:
    return ledger.record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=claim_id,
            source_id=f"source:{evidence_id}",
            source_family=f"family:{evidence_id}",
            channel=channel,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest=f"payload:{evidence_id}",
        )
    )


def test_a16_observation_outcomes_are_exact_and_non_observed_never_bind_evidence():
    _, claim, _ = _knowledge()
    requirement = _requirement(claim)
    evidence_ledger = EvidenceLedger()
    row = _evidence(
        evidence_ledger,
        evidence_id="evidence-observed",
        claim_id=claim.claim_id,
    )

    assert {item.value for item in ObservationOutcome} == {
        "observed",
        "missing",
        "censored",
        "unavailable",
        "timeout",
        "interfered",
    }

    with pytest.raises(ValueError, match="observed result requires evidence"):
        ObservationResultRevision.create(
            requirement=requirement,
            outcome=ObservationOutcome.OBSERVED,
        )

    with pytest.raises(ValueError, match="non-observed result cannot bind evidence"):
        ObservationResultRevision.create(
            requirement=requirement,
            outcome=ObservationOutcome.TIMEOUT,
            evidence=row,
            reason="deadline exceeded",
        )

    for outcome in (
        ObservationOutcome.MISSING,
        ObservationOutcome.CENSORED,
        ObservationOutcome.UNAVAILABLE,
        ObservationOutcome.TIMEOUT,
        ObservationOutcome.INTERFERED,
    ):
        with pytest.raises(ValueError, match="reason must be explicit"):
            ObservationResultRevision.create(
                requirement=requirement,
                outcome=outcome,
            )


def test_a16_observed_result_requires_exact_claim_and_channel_evidence():
    knowledge, claim, unrelated = _knowledge()
    del knowledge
    requirement = _requirement(claim)
    evidence = EvidenceLedger()
    good = _evidence(
        evidence,
        evidence_id="evidence-good",
        claim_id=claim.claim_id,
    )
    observed = ObservationResultRevision.create(
        requirement=requirement,
        outcome=ObservationOutcome.OBSERVED,
        evidence=good,
    )
    assert observed.evidence_id == good.evidence_id
    assert observed.evidence_content_digest == good.content_digest
    assert observed.reason == ""

    wrong_claim = _evidence(
        evidence,
        evidence_id="evidence-wrong-claim",
        claim_id=unrelated.claim_id,
    )
    with pytest.raises(ValueError, match="claim"):
        ObservationResultRevision.create(
            requirement=requirement,
            outcome=ObservationOutcome.OBSERVED,
            evidence=wrong_claim,
        )

    wrong_channel = _evidence(
        evidence,
        evidence_id="evidence-wrong-channel",
        claim_id=claim.claim_id,
        channel=EvidenceChannel.AUDIT,
    )
    with pytest.raises(ValueError, match="channel"):
        ObservationResultRevision.create(
            requirement=requirement,
            outcome=ObservationOutcome.OBSERVED,
            evidence=wrong_channel,
        )


def test_a16_result_ledger_is_append_only_per_exact_requirement_snapshot():
    _, claim, _ = _knowledge()
    requirement = _requirement(claim)
    evidence = EvidenceLedger()
    ledger = ObservationResultLedger()

    first = ledger.register(
        ObservationResultRevision.create(
            requirement=requirement,
            revision=1,
            outcome=ObservationOutcome.TIMEOUT,
            reason="deadline",
        ),
        evidence=evidence,
    )
    assert ledger.current(requirement.digest) == first

    with pytest.raises(ValueError, match="advance exactly once"):
        ledger.register(
            ObservationResultRevision.create(
                requirement=requirement,
                revision=3,
                predecessor_digest=first.digest,
                outcome=ObservationOutcome.MISSING,
                reason="collector gap",
            ),
            evidence=evidence,
        )

    with pytest.raises(ValueError, match="predecessor"):
        ledger.register(
            ObservationResultRevision.create(
                requirement=requirement,
                revision=2,
                predecessor_digest="wrong",
                outcome=ObservationOutcome.MISSING,
                reason="collector gap",
            ),
            evidence=evidence,
        )

    good = _evidence(
        evidence,
        evidence_id="evidence-late",
        claim_id=claim.claim_id,
    )
    second = ledger.register(
        ObservationResultRevision.create(
            requirement=requirement,
            revision=2,
            predecessor_digest=first.digest,
            outcome=ObservationOutcome.OBSERVED,
            evidence=good,
        ),
        evidence=evidence,
    )
    assert ledger.current(requirement.digest) == second
    assert ledger.history(requirement.digest) == (first, second)


def test_a16_result_projection_distinguishes_unrecorded_and_is_relevant_only():
    _, claim, unrelated = _knowledge()
    target_req = _requirement(claim)
    unrelated_req = _requirement(unrelated, "obs.other.001")
    evidence = EvidenceLedger()
    ledger = ObservationResultLedger()

    before = ledger.projection_digest((target_req,))
    state = ledger.projection_state((target_req,))
    assert state["protocol"] == OBSERVATION_RESULT_PROJECTION_PROTOCOL
    assert state["requirements"] == [
        {
            "requirement_digest": target_req.digest,
            "observation_id": target_req.observation_id,
            "status": "unrecorded",
        }
    ]

    ledger.register(
        ObservationResultRevision.create(
            requirement=unrelated_req,
            outcome=ObservationOutcome.MISSING,
            reason="other gap",
        ),
        evidence=evidence,
    )
    assert ledger.projection_digest((target_req,)) == before

    ledger.register(
        ObservationResultRevision.create(
            requirement=target_req,
            outcome=ObservationOutcome.MISSING,
            reason="target gap",
        ),
        evidence=evidence,
    )
    assert ledger.projection_digest((target_req,)) != before
    current = ledger.projection_state((target_req,))["requirements"][0]
    assert current["status"] == ObservationOutcome.MISSING.value
    assert current["revision"]["requirement"]["digest"] == target_req.digest


def test_a16_result_restore_binds_requirement_snapshot_and_evidence_content():
    knowledge, claim, _ = _knowledge()
    requirement = _requirement(claim)
    evidence = EvidenceLedger()
    observed_evidence = _evidence(
        evidence,
        evidence_id="evidence-observed",
        claim_id=claim.claim_id,
    )
    ledger = ObservationResultLedger()
    ledger.register(
        ObservationResultRevision.create(
            requirement=requirement,
            outcome=ObservationOutcome.OBSERVED,
            evidence=observed_evidence,
        ),
        evidence=evidence,
    )
    state = ledger.to_state()
    assert state["protocol"] == OBSERVATION_RESULT_PROTOCOL
    assert ObservationResultLedger.from_state(
        state,
        knowledge=knowledge,
        evidence=evidence,
    ).to_state() == state

    unexpected = dict(state)
    unexpected["extra"] = True
    with pytest.raises(ValueError, match="unexpected"):
        ObservationResultLedger.from_state(
            unexpected,
            knowledge=knowledge,
            evidence=evidence,
        )

    duplicate = dict(state)
    duplicate["revisions"] = [state["revisions"][0], state["revisions"][0]]
    with pytest.raises(ValueError, match="duplicate"):
        ObservationResultLedger.from_state(
            duplicate,
            knowledge=knowledge,
            evidence=evidence,
        )

    requirement_tamper = dict(state)
    revision = dict(state["revisions"][0])
    requirement_state = dict(revision["requirement"])
    requirement_state["claim_content_digest"] = "tampered"
    revision["requirement"] = requirement_state
    requirement_tamper["revisions"] = [revision]
    with pytest.raises(ValueError, match="content digest"):
        ObservationResultLedger.from_state(
            requirement_tamper,
            knowledge=knowledge,
            evidence=evidence,
        )

    evidence_tamper = dict(state)
    revision = dict(state["revisions"][0])
    revision["evidence_content_digest"] = "tampered"
    evidence_tamper["revisions"] = [revision]
    with pytest.raises(ValueError, match="evidence content digest"):
        ObservationResultLedger.from_state(
            evidence_tamper,
            knowledge=knowledge,
            evidence=evidence,
        )
