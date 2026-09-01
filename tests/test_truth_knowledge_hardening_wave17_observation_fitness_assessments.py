from __future__ import annotations

import pytest

from nolane.external_core.evidence_observation_fitness_truth import (
    OBSERVATION_FITNESS_ASSESSMENT_PROJECTION_PROTOCOL,
    ObservationFitness,
    ObservationFitnessAssessmentLedger,
    ObservationFitnessAssessmentRevision,
)
from nolane.external_core.evidence_observation_truth import (
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
from nolane.external_core.knowledge_observation_fitness_truth import ObservationFitnessRequirement
from nolane.external_core.knowledge_observation_truth import ObservationRequirement
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger


def _claim() -> tuple[KnowledgeLedger, KnowledgeClaim]:
    knowledge = KnowledgeLedger()
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-target",
            subject="service",
            relation="healthy",
            object="yes",
        )
    )
    return knowledge, claim


def _observed(
    claim: KnowledgeClaim,
    *,
    observation_id: str = "obs.target.001",
) -> tuple[
    ObservationRequirement,
    ObservationFitnessRequirement,
    EvidenceLedger,
    ObservationResultLedger,
    ObservationResultRevision,
]:
    requirement = ObservationRequirement.create(
        claim=claim,
        observation_id=observation_id,
        channel=EvidenceChannel.TEST,
    )
    fitness_requirement = ObservationFitnessRequirement.create(
        claim=claim,
        observation_requirement=requirement,
    )
    evidence = EvidenceLedger()
    item = evidence.record(
        TruthEvidence.create(
            evidence_id=f"evidence:{observation_id}",
            subject_id=claim.claim_id,
            source_id=f"source:{observation_id}",
            source_family=f"family:{observation_id}",
            channel=EvidenceChannel.TEST,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest=f"payload:{observation_id}",
        )
    )
    results = ObservationResultLedger()
    result = results.register(
        ObservationResultRevision.create(
            requirement=requirement,
            outcome=ObservationOutcome.OBSERVED,
            evidence=item,
        ),
        evidence=evidence,
    )
    return requirement, fitness_requirement, evidence, results, result


def test_a17_fitness_domain_is_discrete_and_assessment_binds_exact_observed_result():
    _, claim = _claim()
    requirement, fitness_requirement, _, _, result = _observed(claim)

    assert {item.value for item in ObservationFitness} == {
        "fit",
        "degraded",
        "invalid",
        "unknown",
    }

    row = ObservationFitnessAssessmentRevision.create(
        fitness_requirement=fitness_requirement,
        observation_result=result,
        fitness=ObservationFitness.FIT,
        assessor_id="calibration-controller",
        method_digest="sha256:method-v1",
        basis_digests=("sha256:calibration-proof",),
    )
    assert row.observation_requirement_digest == requirement.digest
    assert row.observation_result_digest == result.digest
    assert row.evidence_id == result.evidence_id
    assert row.fitness is ObservationFitness.FIT

    missing = ObservationResultRevision.create(
        requirement=requirement,
        outcome=ObservationOutcome.TIMEOUT,
        reason="deadline",
    )
    with pytest.raises(ValueError, match="observed result"):
        ObservationFitnessAssessmentRevision.create(
            fitness_requirement=fitness_requirement,
            observation_result=missing,
            fitness=ObservationFitness.UNKNOWN,
            assessor_id="calibration-controller",
            method_digest="sha256:method-v1",
            basis_digests=("sha256:timeout-proof",),
            reason="fitness cannot be assessed",
        )


def test_a17_fitness_assessment_requires_explicit_lineage_not_numeric_confidence():
    _, claim = _claim()
    _, fitness_requirement, _, _, result = _observed(claim)

    with pytest.raises(ValueError, match="basis"):
        ObservationFitnessAssessmentRevision.create(
            fitness_requirement=fitness_requirement,
            observation_result=result,
            fitness=ObservationFitness.FIT,
            assessor_id="calibration-controller",
            method_digest="sha256:method-v1",
            basis_digests=(),
        )

    with pytest.raises(ValueError, match="reason"):
        ObservationFitnessAssessmentRevision.create(
            fitness_requirement=fitness_requirement,
            observation_result=result,
            fitness=ObservationFitness.DEGRADED,
            assessor_id="calibration-controller",
            method_digest="sha256:method-v1",
            basis_digests=("sha256:drift-report",),
        )


def test_a17_fitness_projection_is_unassessed_until_exact_current_result_is_assessed():
    _, claim = _claim()
    _, fitness_requirement, _, results, result = _observed(claim)
    ledger = ObservationFitnessAssessmentLedger()

    state = ledger.projection_state((fitness_requirement,), observation_results=results)
    assert state["protocol"] == OBSERVATION_FITNESS_ASSESSMENT_PROJECTION_PROTOCOL
    assert state["requirements"][0]["status"] == "unassessed"
    before = ledger.projection_digest((fitness_requirement,), observation_results=results)

    ledger.register(
        ObservationFitnessAssessmentRevision.create(
            fitness_requirement=fitness_requirement,
            observation_result=result,
            fitness=ObservationFitness.FIT,
            assessor_id="calibration-controller",
            method_digest="sha256:method-v1",
            basis_digests=("sha256:calibration-proof",),
        ),
        observation_results=results,
    )
    projection = ledger.projection_state((fitness_requirement,), observation_results=results)
    assert projection["requirements"][0]["status"] == ObservationFitness.FIT.value
    assert ledger.projection_digest(
        (fitness_requirement,), observation_results=results
    ) != before


def test_a17_new_observation_result_snapshot_reopens_fitness_qualification():
    _, claim = _claim()
    requirement, fitness_requirement, evidence, results, first = _observed(claim)
    ledger = ObservationFitnessAssessmentLedger()
    ledger.register(
        ObservationFitnessAssessmentRevision.create(
            fitness_requirement=fitness_requirement,
            observation_result=first,
            fitness=ObservationFitness.FIT,
            assessor_id="calibration-controller",
            method_digest="sha256:method-v1",
            basis_digests=("sha256:calibration-proof",),
        ),
        observation_results=results,
    )
    assert ledger.projection_state(
        (fitness_requirement,), observation_results=results
    )["requirements"][0]["status"] == "fit"

    second = results.register(
        ObservationResultRevision.create(
            requirement=requirement,
            revision=2,
            predecessor_digest=first.digest,
            outcome=ObservationOutcome.OBSERVED,
            evidence=evidence.get(first.evidence_id),
        ),
        evidence=evidence,
    )
    reopened = ledger.projection_state((fitness_requirement,), observation_results=results)
    assert reopened["requirements"][0]["status"] == "unassessed"
    assert reopened["requirements"][0]["observation_result_digest"] == second.digest
