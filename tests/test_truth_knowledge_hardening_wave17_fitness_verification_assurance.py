from __future__ import annotations

import pytest

from nolane.external_core.assurance_observation_fitness_truth import ObservationFitnessTruthClosureCertificate
from nolane.external_core.epistemic_observation_fitness_truth import FITNESS_BINDING_MODE
from nolane.external_core.evidence_truth import EvidenceChannel
from nolane.external_core.knowledge_truth import KnowledgeRisk
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_observation_fitness_truth import (
    ObservationFitnessTruthVerificationLedger,
    ObservationFitnessTruthVerificationReceipt,
)


AS_OF = "2026-09-01T00:00:00Z"


def _receipt() -> ObservationFitnessTruthVerificationReceipt:
    temporal = TemporalContext.create(as_of=AS_OF)
    return ObservationFitnessTruthVerificationReceipt.create(
        receipt_id="receipt:fitness-v11",
        claim_id="claim:fitness-v11",
        verifier_id="verifier:fitness-v11",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest="scope:fitness-v11",
        truth_context_digest="truth-context:fitness-v11",
        temporal_context_digest=temporal.digest,
        as_of=temporal.as_of,
        observation_requirement_digest="observation-requirements:v10",
        observation_result_digest="observation-results:v10",
        fitness_requirement_digest="fitness-requirements:v11",
        fitness_assessment_digest="fitness-assessments:v11",
        evidence_ids=("evidence:verifier-v11",),
        source_provenance_digest="provenance:verifier-v11",
        source_dependence_digest="dependence:verifier-v11",
        evidence_context_digest="evidence-context:verifier-v11",
    )


def _certificate() -> ObservationFitnessTruthClosureCertificate:
    temporal = TemporalContext.create(as_of=AS_OF)
    return ObservationFitnessTruthClosureCertificate.create(
        claim_id="claim:fitness-v11",
        risk=KnowledgeRisk.STANDARD,
        scope_digest="scope:fitness-v11",
        verification_scope_digest="verification:fitness-v11",
        truth_context_digest="truth-context:fitness-v11",
        temporal_context_digest=temporal.digest,
        as_of=temporal.as_of,
        observation_requirement_digest="observation-requirements:v10",
        observation_result_digest="observation-results:v10",
        fitness_requirement_digest="fitness-requirements:v11",
        fitness_assessment_digest="fitness-assessments:v11",
        verification_receipt_ids=("receipt:fitness-v11",),
        epistemic_debt_ids=(),
        closed=True,
        reasons=(),
    )


def test_a17_v11_verification_receipt_binds_both_observation_and_fitness_projections():
    row = _receipt()
    assert row.binding_mode == FITNESS_BINDING_MODE
    assert row.observation_requirement_digest == "observation-requirements:v10"
    assert row.observation_result_digest == "observation-results:v10"
    assert row.fitness_requirement_digest == "fitness-requirements:v11"
    assert row.fitness_assessment_digest == "fitness-assessments:v11"
    assert ObservationFitnessTruthVerificationReceipt.from_state(row.to_state()) == row


def test_a17_v11_assurance_certificate_binds_both_observation_and_fitness_projections():
    row = _certificate()
    assert row.binding_mode == FITNESS_BINDING_MODE
    assert row.fitness_requirement_digest == "fitness-requirements:v11"
    assert row.fitness_assessment_digest == "fitness-assessments:v11"
    assert ObservationFitnessTruthClosureCertificate.from_state(row.to_state()) == row


def test_a17_restore_rejects_v10_masquerade_and_unknown_fields():
    receipt = _receipt().to_state()
    receipt["binding_mode"] = "observation-context-dependence-defeasible-justification-provenance-lineage-temporal-v10"
    with pytest.raises(ValueError, match="binding mode"):
        ObservationFitnessTruthVerificationReceipt.from_state(receipt)

    certificate = _certificate().to_state()
    certificate["legacy_mode"] = True
    with pytest.raises(ValueError, match="unexpected"):
        ObservationFitnessTruthClosureCertificate.from_state(certificate)


def test_a17_verification_ledger_retains_negative_receipts():
    temporal = TemporalContext.create(as_of=AS_OF)
    ledger = ObservationFitnessTruthVerificationLedger()
    negative = ObservationFitnessTruthVerificationReceipt.create(
        receipt_id="receipt:negative-fitness-v11",
        claim_id="claim:fitness-v11",
        verifier_id="verifier:negative-fitness-v11",
        channel=EvidenceChannel.AUDIT,
        passed=False,
        scope_digest="scope:fitness-v11",
        truth_context_digest="truth-context:fitness-v11",
        temporal_context_digest=temporal.digest,
        as_of=temporal.as_of,
        observation_requirement_digest="observation-requirements:v10",
        observation_result_digest="observation-results:v10",
        fitness_requirement_digest="fitness-requirements:v11",
        fitness_assessment_digest="fitness-assessments:v11",
        evidence_ids=("evidence:negative-v11",),
        source_provenance_digest="provenance:negative-v11",
        source_dependence_digest="dependence:negative-v11",
        evidence_context_digest="evidence-context:negative-v11",
    )
    ledger.record(negative)
    assert ledger.receipts("claim:fitness-v11") == (negative,)
