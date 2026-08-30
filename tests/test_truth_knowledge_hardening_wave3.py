from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.external_core.assurance_truth import TruthAssuranceGate
from nolane.external_core.epistemic_truth import (
    EpistemicAssessment,
    EpistemicDisposition,
    EpistemicJudge,
    EpistemicSnapshot,
)
from nolane.external_core.evidence_truth import (
    EvidenceChannel,
    EvidenceLedger,
    EvidencePolarity,
    TruthEvidence,
)
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.verification_truth import TruthVerificationLedger, TruthVerificationReceipt


def evidence(
    evidence_id: str,
    subject_id: str,
    *,
    source_id: str,
    family: str,
    channel: EvidenceChannel,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORT,
) -> TruthEvidence:
    return TruthEvidence.create(
        evidence_id=evidence_id,
        subject_id=subject_id,
        source_id=source_id,
        source_family=family,
        channel=channel,
        polarity=polarity,
        payload_digest=f"payload:{evidence_id}",
    )


def standard_system():
    ev = EvidenceLedger()
    ev.record(evidence(
        "e1", "claim.alpha", source_id="runner-a", family="family-a", channel=EvidenceChannel.TEST,
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.alpha",
        subject="alpha",
        relation="is",
        object="true",
        risk=KnowledgeRisk.STANDARD,
        evidence_ids=("e1",),
    ))
    snapshot = EpistemicJudge().snapshot(knowledge=knowledge, evidence=ev)
    return ev, knowledge, snapshot


def verification_for(snapshot: EpistemicSnapshot, knowledge: KnowledgeLedger, *,
                     receipt_id: str = "v1", verifier_id: str = "runner-a",
                     family: str = "family-a", channel: EvidenceChannel = EvidenceChannel.TEST,
                     evidence_ids: tuple[str, ...] = ("e1",)) -> TruthVerificationLedger:
    ledger = TruthVerificationLedger()
    ledger.record(TruthVerificationReceipt.create(
        receipt_id=receipt_id,
        claim_id="claim.alpha",
        verifier_id=verifier_id,
        source_family=family,
        channel=channel,
        passed=True,
        knowledge_digest=knowledge.digest,
        epistemic_digest=snapshot.digest,
        evidence_ids=evidence_ids,
    ))
    return ledger


def test_cross_subject_evidence_cannot_be_laundered_into_another_claim():
    ev = EvidenceLedger()
    ev.record(evidence(
        "e-other", "claim.other", source_id="runner-a", family="family-a", channel=EvidenceChannel.TEST,
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.alpha", subject="alpha", relation="is", object="true",
        evidence_ids=("e-other",),
    ))

    judge = EpistemicJudge()
    assessment = judge.assess("claim.alpha", knowledge=knowledge, evidence=ev)
    snapshot = judge.snapshot(knowledge=knowledge, evidence=ev)

    assert assessment.disposition is EpistemicDisposition.UNKNOWN
    assert any(
        debt.claim_id == "claim.alpha" and debt.reason == "evidence_subject_mismatch"
        for debt in snapshot.debts
    )


def test_one_source_identity_cannot_rebind_to_multiple_source_families():
    ev = EvidenceLedger()
    ev.record(evidence(
        "e1", "claim.alpha", source_id="same-source", family="family-a", channel=EvidenceChannel.TEST,
    ))
    with pytest.raises(ValueError, match="source identity family rebinding"):
        ev.record(evidence(
            "e2", "claim.beta", source_id="same-source", family="family-b", channel=EvidenceChannel.TEST,
        ))


def test_strict_closure_rejects_stale_snapshot_replay_after_live_evidence_changes():
    ev, knowledge, snapshot = standard_system()
    verification = verification_for(snapshot, knowledge)
    gate = TruthAssuranceGate()

    closed = gate.close_snapshot(
        claim_id="claim.alpha", knowledge=knowledge, evidence=ev,
        epistemic=snapshot, verification=verification,
    )
    assert closed.closed
    assert closed.evidence_digest == ev.digest

    ev.revoke("e1", reason="withdrawn after closure candidate")
    with pytest.raises(ValueError, match="different evidence state"):
        gate.close_snapshot(
            claim_id="claim.alpha", knowledge=knowledge, evidence=ev,
            epistemic=snapshot, verification=verification,
        )


def test_assurance_recomputes_epistemic_state_instead_of_trusting_forged_snapshot():
    ev = EvidenceLedger()
    ev.record(evidence(
        "e1", "claim.alpha", source_id="runner-a", family="family-a",
        channel=EvidenceChannel.TEST, polarity=EvidencePolarity.REFUTE,
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.alpha", subject="alpha", relation="is", object="true", evidence_ids=("e1",),
    ))
    canonical = EpistemicJudge().snapshot(knowledge=knowledge, evidence=ev)
    assert canonical.assessment("claim.alpha").disposition is EpistemicDisposition.REFUTED

    forged_assessment = EpistemicAssessment.create(
        claim_id="claim.alpha",
        disposition=EpistemicDisposition.SUPPORTED,
        support_evidence_ids=("e1",),
        refute_evidence_ids=(),
        knowledge_digest=knowledge.digest,
        evidence_digest=ev.digest,
    )
    forged = EpistemicSnapshot.create(
        knowledge_digest=knowledge.digest,
        evidence_digest=ev.digest,
        assessments=(forged_assessment,),
        contradictions=(),
        debts=(),
    )
    verification = verification_for(forged, knowledge)

    with pytest.raises(ValueError, match="noncanonical epistemic snapshot"):
        TruthAssuranceGate().close_snapshot(
            claim_id="claim.alpha", knowledge=knowledge, evidence=ev,
            epistemic=forged, verification=verification,
        )


def test_verification_identity_family_and_channel_must_be_grounded_in_cited_evidence():
    ev, knowledge, snapshot = standard_system()
    gate = TruthAssuranceGate()

    forged_family = verification_for(snapshot, knowledge, family="invented-family")
    result = gate.close_snapshot(
        claim_id="claim.alpha", knowledge=knowledge, evidence=ev,
        epistemic=snapshot, verification=forged_family,
    )
    assert not result.closed
    assert "verification_provenance_mismatch" in result.reasons

    forged_channel = verification_for(snapshot, knowledge, channel=EvidenceChannel.REPRODUCTION)
    result = gate.close_snapshot(
        claim_id="claim.alpha", knowledge=knowledge, evidence=ev,
        epistemic=snapshot, verification=forged_channel,
    )
    assert not result.closed
    assert "verification_provenance_mismatch" in result.reasons

    forged_verifier = verification_for(snapshot, knowledge, verifier_id="not-the-evidence-source")
    result = gate.close_snapshot(
        claim_id="claim.alpha", knowledge=knowledge, evidence=ev,
        epistemic=snapshot, verification=forged_verifier,
    )
    assert not result.closed
    assert "verification_provenance_mismatch" in result.reasons


def test_unbound_or_inactive_verification_evidence_never_counts_for_closure():
    ev, knowledge, snapshot = standard_system()
    gate = TruthAssuranceGate()

    unbound = verification_for(snapshot, knowledge, evidence_ids=())
    result = gate.close_snapshot(
        claim_id="claim.alpha", knowledge=knowledge, evidence=ev,
        epistemic=snapshot, verification=unbound,
    )
    assert not result.closed
    assert "unbound_verification_evidence" in result.reasons


def test_unbound_legacy_close_path_is_permanently_fail_closed():
    verification = TruthVerificationLedger()
    verification.record(TruthVerificationReceipt.create(
        receipt_id="v1", claim_id="claim.alpha", verifier_id="invented",
        source_family="invented", channel=EvidenceChannel.TEST, passed=True,
        knowledge_digest="invented-k", epistemic_digest="invented-e",
    ))
    result = TruthAssuranceGate().close(
        claim_id="claim.alpha", risk=KnowledgeRisk.LOW,
        knowledge_digest="invented-k", epistemic_digest="invented-e", verification=verification,
    )
    assert not result.closed
    assert "noncanonical_closure_path" in result.reasons


def test_knowledge_restore_is_protocol_checked_and_independent_of_claim_id_sort_order():
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="z.parent", subject="parent", relation="is", object="valid",
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="a.child", subject="child", relation="depends", object="parent",
        parent_claim_ids=("z.parent",),
    ))
    state = knowledge.to_state()
    assert [row["claim_id"] for row in state["claims"]] == ["a.child", "z.parent"]
    restored = KnowledgeLedger.from_state(state)
    assert restored.digest == knowledge.digest

    tampered = deepcopy(state)
    tampered["protocol"] = "forged-knowledge-protocol"
    with pytest.raises(ValueError, match="unsupported knowledge protocol"):
        KnowledgeLedger.from_state(tampered)


def test_epistemic_snapshot_roundtrip_is_content_addressed_and_tamper_evident():
    ev, knowledge, snapshot = standard_system()
    state = snapshot.to_state()
    assert EpistemicSnapshot.from_state(state) == snapshot

    tampered = deepcopy(state)
    tampered["assessments"][0]["disposition"] = EpistemicDisposition.REFUTED.value
    with pytest.raises(ValueError, match="epistemic assessment digest mismatch"):
        EpistemicSnapshot.from_state(tampered)
