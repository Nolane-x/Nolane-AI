from __future__ import annotations

from nolane.external_core.assurance_truth import TruthClosureCertificate
from nolane.external_core.evidence_truth import EvidenceChannel
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeRisk
from nolane.external_core.verification_truth import TruthVerificationReceipt


def test_knowledge_claim_reference_sets_have_order_independent_identity():
    left = KnowledgeClaim.create(
        claim_id="claim.alpha", subject="alpha", relation="is", object="true",
        risk=KnowledgeRisk.HIGH,
        evidence_ids=("e2", "e1"),
        parent_claim_ids=("p2", "p1"),
    )
    right = KnowledgeClaim.create(
        claim_id="claim.alpha", subject="alpha", relation="is", object="true",
        risk=KnowledgeRisk.HIGH,
        evidence_ids=("e1", "e2"),
        parent_claim_ids=("p1", "p2"),
    )
    assert left == right
    assert left.evidence_ids == ("e1", "e2")
    assert left.parent_claim_ids == ("p1", "p2")


def test_verification_evidence_reference_set_has_order_independent_identity():
    left = TruthVerificationReceipt.create(
        receipt_id="v1", claim_id="claim.alpha", verifier_id="runner",
        source_family="family", channel=EvidenceChannel.TEST, passed=True,
        knowledge_digest="knowledge", epistemic_digest="epistemic",
        evidence_ids=("e2", "e1"),
    )
    right = TruthVerificationReceipt.create(
        receipt_id="v1", claim_id="claim.alpha", verifier_id="runner",
        source_family="family", channel=EvidenceChannel.TEST, passed=True,
        knowledge_digest="knowledge", epistemic_digest="epistemic",
        evidence_ids=("e1", "e2"),
    )
    assert left == right
    assert left.evidence_ids == ("e1", "e2")


def test_closure_certificate_set_semantics_are_canonically_ordered():
    left = TruthClosureCertificate.create(
        claim_id="claim.alpha", risk=KnowledgeRisk.HIGH,
        knowledge_digest="knowledge", evidence_digest="evidence",
        epistemic_digest="epistemic", verification_digest="verification",
        verification_receipt_ids=("v2", "v1"),
        epistemic_debt_ids=("d2", "d1"),
        closed=False,
        reasons=("reason-z", "reason-a"),
    )
    right = TruthClosureCertificate.create(
        claim_id="claim.alpha", risk=KnowledgeRisk.HIGH,
        knowledge_digest="knowledge", evidence_digest="evidence",
        epistemic_digest="epistemic", verification_digest="verification",
        verification_receipt_ids=("v1", "v2"),
        epistemic_debt_ids=("d1", "d2"),
        closed=False,
        reasons=("reason-a", "reason-z"),
    )
    assert left == right
    assert left.verification_receipt_ids == ("v1", "v2")
    assert left.epistemic_debt_ids == ("d1", "d2")
    assert left.reasons == ("reason-a", "reason-z")
