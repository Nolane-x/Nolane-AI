from __future__ import annotations

import pytest

from nolane.external_core.assurance_truth import TruthAssuranceGate
from nolane.external_core.epistemic_truth import EpistemicDisposition, EpistemicJudge
from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.verification_truth import TruthVerificationLedger, TruthVerificationReceipt


def evidence(evidence_id: str, subject_id: str, *, family: str, channel: EvidenceChannel, polarity=EvidencePolarity.SUPPORT):
    return TruthEvidence.create(
        evidence_id=evidence_id, subject_id=subject_id, source_id=f"source:{evidence_id}",
        source_family=family, channel=channel, polarity=polarity, payload_digest=f"payload:{evidence_id}",
    )


def test_snapshot_preserves_competing_supported_propositions_and_critical_debt():
    ev = EvidenceLedger()
    ev.record(evidence("e-true", "claim.true", family="fa", channel=EvidenceChannel.TEST))
    ev.record(evidence("e-false", "claim.false", family="fb", channel=EvidenceChannel.REPRODUCTION))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(claim_id="claim.true", subject="alpha", relation="is", object="true", risk=KnowledgeRisk.CRITICAL, evidence_ids=("e-true",)))
    knowledge.add(KnowledgeClaim.create(claim_id="claim.false", subject="alpha", relation="is", object="false", risk=KnowledgeRisk.CRITICAL, evidence_ids=("e-false",)))
    snapshot = EpistemicJudge().snapshot(knowledge=knowledge, evidence=ev)
    assert len(snapshot.contradictions) == 1
    assert snapshot.contradictions[0].claim_ids == ("claim.false", "claim.true")
    assert snapshot.contradictions[0].object_values == ("false", "true")
    assert any(row.critical and row.reason == "competing_supported_propositions" for row in snapshot.debts)


def test_derived_claim_is_unknown_when_parent_is_refuted():
    ev = EvidenceLedger()
    ev.record(evidence("base-refute", "claim.base", family="fa", channel=EvidenceChannel.TEST, polarity=EvidencePolarity.REFUTE))
    ev.record(evidence("derived-support", "claim.derived", family="fb", channel=EvidenceChannel.TEST))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(claim_id="claim.base", subject="base", relation="is", object="true", evidence_ids=("base-refute",)))
    knowledge.add(KnowledgeClaim.create(claim_id="claim.derived", subject="derived", relation="depends", object="base", evidence_ids=("derived-support",), parent_claim_ids=("claim.base",)))
    assert EpistemicJudge().assess("claim.derived", knowledge=knowledge, evidence=ev).disposition is EpistemicDisposition.UNKNOWN


def test_strict_assurance_binds_canonical_snapshot_and_rejects_stale_verification():
    ev = EvidenceLedger()
    ev.record(evidence("e1", "claim.alpha", family="fa", channel=EvidenceChannel.TEST))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(claim_id="claim.alpha", subject="alpha", relation="is", object="true", risk=KnowledgeRisk.HIGH, evidence_ids=("e1",)))
    snapshot = EpistemicJudge().snapshot(knowledge=knowledge, evidence=ev)
    verification = TruthVerificationLedger()
    verification.record(TruthVerificationReceipt.create(receipt_id="v1", claim_id="claim.alpha", verifier_id="a", source_family="fa", channel=EvidenceChannel.TEST, passed=True, knowledge_digest=knowledge.digest, epistemic_digest=snapshot.digest))
    verification.record(TruthVerificationReceipt.create(receipt_id="v2", claim_id="claim.alpha", verifier_id="b", source_family="fb", channel=EvidenceChannel.REPRODUCTION, passed=True, knowledge_digest=knowledge.digest, epistemic_digest=snapshot.digest))
    gate = TruthAssuranceGate()
    assert gate.close_snapshot(claim_id="claim.alpha", knowledge=knowledge, epistemic=snapshot, verification=verification).closed
    ev.revoke("e1", reason="withdrawn")
    changed = EpistemicJudge().snapshot(knowledge=knowledge, evidence=ev)
    stale = gate.close_snapshot(claim_id="claim.alpha", knowledge=knowledge, epistemic=changed, verification=verification)
    assert not stale.closed
    assert "epistemic_claim_not_supported" in stale.reasons
    assert "insufficient_independent_verification" in stale.reasons


def test_truth_ledgers_restore_fail_closed_on_tamper():
    ev = EvidenceLedger(); ev.record(evidence("e1", "claim.alpha", family="fa", channel=EvidenceChannel.TEST))
    state = ev.to_state(); assert EvidenceLedger.from_state(state).digest == ev.digest
    forged = {**state, "records": [dict(state["records"][0])]}; forged["records"][0]["source_family"] = "forged"
    with pytest.raises(ValueError, match="evidence content digest mismatch"):
        EvidenceLedger.from_state(forged)
    verification = TruthVerificationLedger(); verification.record(TruthVerificationReceipt.create(receipt_id="v1", claim_id="claim.alpha", verifier_id="a", source_family="fa", channel=EvidenceChannel.TEST, passed=False, knowledge_digest="k", epistemic_digest="e"))
    vstate = verification.to_state(); assert TruthVerificationLedger.from_state(vstate).receipts() == verification.receipts()
    tampered = {**vstate, "receipts": [dict(vstate["receipts"][0])]}; tampered["receipts"][0]["passed"] = True
    with pytest.raises(ValueError, match="truth verification receipt digest mismatch"):
        TruthVerificationLedger.from_state(tampered)
