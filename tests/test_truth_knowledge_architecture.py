from __future__ import annotations

import pytest

from nolane.external_core.assurance_truth import TruthAssuranceGate
from nolane.external_core.epistemic_truth import EpistemicDisposition, EpistemicJudge
from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.verification_truth import TruthVerificationLedger, TruthVerificationReceipt


def _evidence(evidence_id: str, *, source: str, family: str, channel: EvidenceChannel, polarity=EvidencePolarity.SUPPORT,
              subject_id: str = "claim.alpha"):
    return TruthEvidence.create(
        evidence_id=evidence_id,
        subject_id=subject_id,
        source_id=source,
        source_family=family,
        channel=channel,
        polarity=polarity,
        payload_digest=f"payload:{evidence_id}",
    )


def test_knowledge_is_content_addressed_and_revocation_propagates_to_derived_claims():
    evidence = EvidenceLedger()
    evidence.record(_evidence("e1", source="s1", family="f1", channel=EvidenceChannel.TEST))
    knowledge = KnowledgeLedger()
    base = KnowledgeClaim.create(
        claim_id="claim.alpha", subject="alpha", relation="is", object="true",
        risk=KnowledgeRisk.HIGH, evidence_ids=("e1",),
    )
    derived = KnowledgeClaim.create(
        claim_id="claim.beta", subject="beta", relation="depends-on", object="alpha",
        risk=KnowledgeRisk.STANDARD, parent_claim_ids=("claim.alpha",),
    )
    knowledge.add(base)
    knowledge.add(derived)
    before = knowledge.digest
    assert knowledge.impacted_claim_ids(evidence) == ()
    evidence.revoke("e1", reason="source withdrawn")
    assert knowledge.impacted_claim_ids(evidence) == ("claim.alpha", "claim.beta")
    assert knowledge.digest == before


def test_correlated_mirrors_do_not_count_as_independent_verification_channels():
    ledger = TruthVerificationLedger()
    for receipt_id, source in (("v1", "mirror-a"), ("v2", "mirror-b")):
        ledger.record(TruthVerificationReceipt.create(
            receipt_id=receipt_id, claim_id="claim.alpha", verifier_id=source,
            source_family="same-upstream", channel=EvidenceChannel.REPRODUCTION,
            passed=True, knowledge_digest="k", epistemic_digest="e",
        ))
    assert ledger.independent_passing_channels("claim.alpha", knowledge_digest="k", epistemic_digest="e") == 1


def test_contradiction_and_unknown_are_first_class_epistemic_states():
    evidence = EvidenceLedger()
    evidence.record(_evidence("yes", source="a", family="fa", channel=EvidenceChannel.TEST))
    evidence.record(_evidence("no", source="b", family="fb", channel=EvidenceChannel.TEST, polarity=EvidencePolarity.REFUTE))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.alpha", subject="alpha", relation="is", object="true",
        risk=KnowledgeRisk.CRITICAL, evidence_ids=("yes", "no"),
    ))
    judge = EpistemicJudge()
    assessment = judge.assess("claim.alpha", knowledge=knowledge, evidence=evidence)
    assert assessment.disposition is EpistemicDisposition.CONTRADICTED
    assert assessment.support_evidence_ids == ("yes",)
    assert assessment.refute_evidence_ids == ("no",)

    unknown = KnowledgeClaim.create(
        claim_id="claim.unknown", subject="unknown", relation="is", object="?",
        risk=KnowledgeRisk.CRITICAL,
    )
    knowledge.add(unknown)
    assert judge.assess("claim.unknown", knowledge=knowledge, evidence=evidence).disposition is EpistemicDisposition.UNKNOWN


def test_negative_verification_is_retained_and_exact_state_binding_rejects_stale_receipts():
    ledger = TruthVerificationLedger()
    failed = TruthVerificationReceipt.create(
        receipt_id="v-neg", claim_id="claim.alpha", verifier_id="red-team",
        source_family="red-team", channel=EvidenceChannel.ADVERSARIAL,
        passed=False, knowledge_digest="k1", epistemic_digest="e1",
    )
    ledger.record(failed)
    assert ledger.receipts("claim.alpha") == (failed,)
    assert ledger.bound_receipts("claim.alpha", knowledge_digest="k2", epistemic_digest="e1") == ()


def test_high_risk_truth_closure_needs_independent_channels_and_critical_debt_blocks_closure():
    evidence = EvidenceLedger()
    evidence.record(_evidence("e1", source="runner-a", family="family-a", channel=EvidenceChannel.TEST))
    evidence.record(_evidence("e2", source="runner-b", family="family-b", channel=EvidenceChannel.REPRODUCTION))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.alpha", subject="alpha", relation="is", object="true",
        risk=KnowledgeRisk.HIGH, evidence_ids=("e1", "e2"),
    ))
    snapshot = EpistemicJudge().snapshot(knowledge=knowledge, evidence=evidence)

    verification = TruthVerificationLedger()
    verification.record(TruthVerificationReceipt.create(
        receipt_id="v1", claim_id="claim.alpha", verifier_id="runner-a",
        source_family="family-a", channel=EvidenceChannel.TEST, passed=True,
        knowledge_digest=knowledge.digest, epistemic_digest=snapshot.digest, evidence_ids=("e1",),
    ))
    gate = TruthAssuranceGate()
    rejected = gate.close_snapshot(
        claim_id="claim.alpha", knowledge=knowledge, evidence=evidence,
        epistemic=snapshot, verification=verification,
    )
    assert not rejected.closed
    assert "insufficient_independent_verification" in rejected.reasons

    verification.record(TruthVerificationReceipt.create(
        receipt_id="v2", claim_id="claim.alpha", verifier_id="runner-b",
        source_family="family-b", channel=EvidenceChannel.REPRODUCTION, passed=True,
        knowledge_digest=knowledge.digest, epistemic_digest=snapshot.digest, evidence_ids=("e2",),
    ))
    closed = gate.close_snapshot(
        claim_id="claim.alpha", knowledge=knowledge, evidence=evidence,
        epistemic=snapshot, verification=verification,
    )
    assert closed.closed
    restored = type(closed).from_state(closed.to_state())
    assert restored == closed

    critical_evidence = EvidenceLedger()
    critical_knowledge = KnowledgeLedger()
    critical_knowledge.add(KnowledgeClaim.create(
        claim_id="claim.critical", subject="critical", relation="is", object="unresolved",
        risk=KnowledgeRisk.CRITICAL,
    ))
    critical_snapshot = EpistemicJudge().snapshot(knowledge=critical_knowledge, evidence=critical_evidence)
    blocked = gate.close_snapshot(
        claim_id="claim.critical", knowledge=critical_knowledge, evidence=critical_evidence,
        epistemic=critical_snapshot, verification=TruthVerificationLedger(),
    )
    assert not blocked.closed
    assert "critical_epistemic_debt" in blocked.reasons


def test_duplicate_or_unbound_verification_identity_fails_closed():
    ledger = TruthVerificationLedger()
    row = TruthVerificationReceipt.create(
        receipt_id="v1", claim_id="claim.alpha", verifier_id="runner-a",
        source_family="family-a", channel=EvidenceChannel.TEST, passed=True,
        knowledge_digest="k", epistemic_digest="e",
    )
    ledger.record(row)
    with pytest.raises(ValueError, match="receipt id collision"):
        ledger.record(TruthVerificationReceipt.create(
            receipt_id="v1", claim_id="claim.alpha", verifier_id="runner-x",
            source_family="family-x", channel=EvidenceChannel.TEST, passed=True,
            knowledge_digest="k", epistemic_digest="e",
        ))
