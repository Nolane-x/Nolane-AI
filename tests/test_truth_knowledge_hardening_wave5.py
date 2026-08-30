from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.external_core.assurance_truth import TruthAssuranceGate, TruthClosureCertificate
from nolane.external_core.epistemic_truth import EpistemicJudge
from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.verification_truth import TruthVerificationLedger, TruthVerificationReceipt


def _evidence(evidence_id: str = "e1") -> TruthEvidence:
    return TruthEvidence.create(
        evidence_id=evidence_id,
        subject_id="claim.alpha",
        source_id="runner-a",
        source_family="family-a",
        channel=EvidenceChannel.TEST,
        polarity=EvidencePolarity.SUPPORT,
        payload_digest=f"payload:{evidence_id}",
    )


def _system():
    evidence = EvidenceLedger()
    evidence.record(_evidence())
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.alpha",
        subject="alpha",
        relation="is",
        object="true",
        risk=KnowledgeRisk.STANDARD,
        evidence_ids=("e1",),
    ))
    snapshot = EpistemicJudge().snapshot(knowledge=knowledge, evidence=evidence)
    return evidence, knowledge, snapshot


def _passing_verification(knowledge: KnowledgeLedger, snapshot) -> TruthVerificationLedger:
    verification = TruthVerificationLedger()
    verification.record(TruthVerificationReceipt.create(
        receipt_id="v1",
        claim_id="claim.alpha",
        verifier_id="runner-a",
        source_family="family-a",
        channel=EvidenceChannel.TEST,
        passed=True,
        knowledge_digest=knowledge.digest,
        epistemic_digest=snapshot.digest,
        evidence_ids=("e1",),
    ))
    return verification


def test_digest_valid_self_issued_closed_certificate_is_not_authority_without_live_revalidation():
    evidence, knowledge, snapshot = _system()
    verification = TruthVerificationLedger()
    forged = TruthClosureCertificate.create(
        claim_id="claim.alpha",
        risk=KnowledgeRisk.STANDARD,
        knowledge_digest=knowledge.digest,
        evidence_digest=evidence.digest,
        epistemic_digest=snapshot.digest,
        verification_digest=verification.digest,
        verification_receipt_ids=(),
        epistemic_debt_ids=(),
        closed=True,
        reasons=(),
    )
    restored = TruthClosureCertificate.from_state(forged.to_state())
    assert restored.closed
    assert not TruthAssuranceGate().validate_certificate(
        restored,
        knowledge=knowledge,
        evidence=evidence,
        verification=verification,
    )


def test_genuine_certificate_validates_only_against_the_live_state_that_authorized_it():
    evidence, knowledge, snapshot = _system()
    verification = _passing_verification(knowledge, snapshot)
    gate = TruthAssuranceGate()
    certificate = gate.close_live(
        claim_id="claim.alpha", knowledge=knowledge, evidence=evidence, verification=verification,
    )
    assert certificate.closed
    assert gate.validate_certificate(
        certificate, knowledge=knowledge, evidence=evidence, verification=verification,
    )

    evidence.revoke("e1", reason="withdrawn after issuance")
    assert not gate.validate_certificate(
        certificate, knowledge=knowledge, evidence=evidence, verification=verification,
    )


def test_evidence_restore_rejects_duplicate_serialized_records_and_revocations():
    evidence = EvidenceLedger()
    evidence.record(_evidence())
    duplicate_record = deepcopy(evidence.to_state())
    duplicate_record["records"].append(deepcopy(duplicate_record["records"][0]))
    with pytest.raises(ValueError, match="duplicate serialized evidence id"):
        EvidenceLedger.from_state(duplicate_record)

    evidence.revoke("e1", reason="withdrawn")
    duplicate_revocation = deepcopy(evidence.to_state())
    duplicate_revocation["revocations"].append(deepcopy(duplicate_revocation["revocations"][0]))
    with pytest.raises(ValueError, match="duplicate serialized evidence revocation"):
        EvidenceLedger.from_state(duplicate_revocation)


def test_knowledge_restore_rejects_duplicate_serialized_claim_rows():
    _, knowledge, _ = _system()
    state = deepcopy(knowledge.to_state())
    state["claims"].append(deepcopy(state["claims"][0]))
    with pytest.raises(ValueError, match="duplicate serialized knowledge claim id"):
        KnowledgeLedger.from_state(state)


def test_verification_restore_rejects_duplicate_serialized_receipts():
    evidence, knowledge, snapshot = _system()
    verification = _passing_verification(knowledge, snapshot)
    state = deepcopy(verification.to_state())
    state["receipts"].append(deepcopy(state["receipts"][0]))
    with pytest.raises(ValueError, match="duplicate serialized verification receipt id"):
        TruthVerificationLedger.from_state(state)


def test_closure_certificate_rejects_duplicate_receipt_and_debt_identity_lists():
    with pytest.raises(ValueError, match="verification receipt ids must be unique"):
        TruthClosureCertificate.create(
            claim_id="claim.alpha", risk=KnowledgeRisk.STANDARD,
            knowledge_digest="k", evidence_digest="evidence", epistemic_digest="epistemic",
            verification_digest="verification", verification_receipt_ids=("v1", "v1"),
            epistemic_debt_ids=(), closed=False, reasons=("duplicate",),
        )
    with pytest.raises(ValueError, match="epistemic debt ids must be unique"):
        TruthClosureCertificate.create(
            claim_id="claim.alpha", risk=KnowledgeRisk.STANDARD,
            knowledge_digest="k", evidence_digest="evidence", epistemic_digest="epistemic",
            verification_digest="verification", verification_receipt_ids=(),
            epistemic_debt_ids=("d1", "d1"), closed=False, reasons=("duplicate",),
        )
