from __future__ import annotations

import copy

from nolane.external_core.assurance_truth import TruthAssuranceGate
from nolane.external_core.epistemic_truth import EpistemicDisposition, EpistemicJudge
from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.verification_truth import TruthVerificationLedger, TruthVerificationReceipt


def _evidence(
    evidence_id: str,
    *,
    subject_id: str,
    source_id: str,
    source_family: str,
    channel: EvidenceChannel,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORT,
) -> TruthEvidence:
    return TruthEvidence.create(
        evidence_id=evidence_id,
        subject_id=subject_id,
        source_id=source_id,
        source_family=source_family,
        channel=channel,
        polarity=polarity,
        payload_digest=f"payload:{evidence_id}",
    )


def _record_current_receipt(
    ledger: TruthVerificationLedger,
    *,
    receipt_id: str,
    claim_id: str,
    verifier_id: str,
    source_family: str,
    channel: EvidenceChannel,
    passed: bool,
    evidence_ids: tuple[str, ...],
    knowledge: KnowledgeLedger,
    evidence: EvidenceLedger,
) -> TruthVerificationReceipt:
    judge = EpistemicJudge()
    scope_builder = getattr(judge, "dependency_scope", None)
    if scope_builder is not None:
        scope = scope_builder(claim_id, knowledge=knowledge, evidence=evidence)
        row = TruthVerificationReceipt.create(
            receipt_id=receipt_id,
            claim_id=claim_id,
            verifier_id=verifier_id,
            source_family=source_family,
            channel=channel,
            passed=passed,
            scope_digest=scope.digest,
            evidence_ids=evidence_ids,
        )
    else:
        snapshot = judge.snapshot(knowledge=knowledge, evidence=evidence)
        row = TruthVerificationReceipt.create(
            receipt_id=receipt_id,
            claim_id=claim_id,
            verifier_id=verifier_id,
            source_family=source_family,
            channel=channel,
            passed=passed,
            knowledge_digest=knowledge.digest,
            epistemic_digest=snapshot.digest,
            evidence_ids=evidence_ids,
        )
    ledger.record(row)
    return row


def _build_high_risk_target():
    evidence = EvidenceLedger()
    evidence.record(_evidence(
        "target-e1", subject_id="claim.target", source_id="runner-a", source_family="family-a",
        channel=EvidenceChannel.TEST,
    ))
    evidence.record(_evidence(
        "target-e2", subject_id="claim.target", source_id="runner-b", source_family="family-b",
        channel=EvidenceChannel.REPRODUCTION,
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.target", subject="target", relation="is", object="true",
        risk=KnowledgeRisk.HIGH, evidence_ids=("target-e1", "target-e2"),
    ))
    verification = TruthVerificationLedger()
    _record_current_receipt(
        verification, receipt_id="target-v1", claim_id="claim.target", verifier_id="runner-a",
        source_family="family-a", channel=EvidenceChannel.TEST, passed=True,
        evidence_ids=("target-e1",), knowledge=knowledge, evidence=evidence,
    )
    _record_current_receipt(
        verification, receipt_id="target-v2", claim_id="claim.target", verifier_id="runner-b",
        source_family="family-b", channel=EvidenceChannel.REPRODUCTION, passed=True,
        evidence_ids=("target-e2",), knowledge=knowledge, evidence=evidence,
    )
    return knowledge, evidence, verification


def _build_derived_target():
    evidence = EvidenceLedger()
    evidence.record(_evidence(
        "parent-e", subject_id="claim.parent", source_id="parent-source", source_family="parent-family",
        channel=EvidenceChannel.TEST,
    ))
    evidence.record(_evidence(
        "child-e", subject_id="claim.child", source_id="child-source", source_family="child-family",
        channel=EvidenceChannel.REPRODUCTION,
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.parent", subject="parent", relation="state", object="valid",
        risk=KnowledgeRisk.STANDARD, evidence_ids=("parent-e",),
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.child", subject="child", relation="depends", object="parent",
        risk=KnowledgeRisk.STANDARD, evidence_ids=("child-e",), parent_claim_ids=("claim.parent",),
    ))
    verification = TruthVerificationLedger()
    _record_current_receipt(
        verification, receipt_id="child-v", claim_id="claim.child", verifier_id="child-source",
        source_family="child-family", channel=EvidenceChannel.REPRODUCTION, passed=True,
        evidence_ids=("child-e",), knowledge=knowledge, evidence=evidence,
    )
    return knowledge, evidence, verification


def test_a8_unrelated_knowledge_and_evidence_do_not_stale_live_certificate():
    knowledge, evidence, verification = _build_high_risk_target()
    gate = TruthAssuranceGate()
    certificate = gate.close_live(
        claim_id="claim.target", knowledge=knowledge, evidence=evidence, verification=verification,
    )
    assert certificate.closed
    assert getattr(certificate, "binding_mode", None) == "dependency-scope-v2"

    evidence.record(_evidence(
        "unrelated-e", subject_id="claim.unrelated", source_id="unrelated-source",
        source_family="unrelated-family", channel=EvidenceChannel.OBSERVATION,
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.unrelated", subject="elsewhere", relation="is", object="irrelevant",
        risk=KnowledgeRisk.LOW, evidence_ids=("unrelated-e",),
    ))

    assert gate.validate_certificate(
        certificate, knowledge=knowledge, evidence=evidence, verification=verification,
    )


def test_a8_unrelated_verification_receipt_does_not_stale_live_certificate():
    knowledge, evidence, verification = _build_high_risk_target()
    gate = TruthAssuranceGate()
    certificate = gate.close_live(
        claim_id="claim.target", knowledge=knowledge, evidence=evidence, verification=verification,
    )
    assert certificate.closed

    evidence.record(_evidence(
        "other-e", subject_id="claim.other", source_id="other-source", source_family="other-family",
        channel=EvidenceChannel.AUDIT,
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.other", subject="other", relation="is", object="true",
        risk=KnowledgeRisk.LOW, evidence_ids=("other-e",),
    ))
    _record_current_receipt(
        verification, receipt_id="other-v", claim_id="claim.other", verifier_id="other-source",
        source_family="other-family", channel=EvidenceChannel.AUDIT, passed=True,
        evidence_ids=("other-e",), knowledge=knowledge, evidence=evidence,
    )

    assert gate.validate_certificate(
        certificate, knowledge=knowledge, evidence=evidence, verification=verification,
    )


def test_a8_target_evidence_revocation_invalidates_scoped_certificate():
    knowledge, evidence, verification = _build_high_risk_target()
    gate = TruthAssuranceGate()
    certificate = gate.close_live(
        claim_id="claim.target", knowledge=knowledge, evidence=evidence, verification=verification,
    )
    assert certificate.closed
    evidence.revoke("target-e1", reason="withdrawn")
    assert not gate.validate_certificate(
        certificate, knowledge=knowledge, evidence=evidence, verification=verification,
    )


def test_a8_ancestor_evidence_revocation_invalidates_descendant_certificate():
    knowledge, evidence, verification = _build_derived_target()
    gate = TruthAssuranceGate()
    certificate = gate.close_live(
        claim_id="claim.child", knowledge=knowledge, evidence=evidence, verification=verification,
    )
    assert certificate.closed
    evidence.revoke("parent-e", reason="parent source withdrawn")
    assert not gate.validate_certificate(
        certificate, knowledge=knowledge, evidence=evidence, verification=verification,
    )


def test_a8_supported_competitor_for_target_blocks_scoped_closure():
    knowledge, evidence, verification = _build_high_risk_target()
    evidence.record(_evidence(
        "competitor-e", subject_id="claim.target.alt", source_id="competitor-source",
        source_family="competitor-family", channel=EvidenceChannel.ADVERSARIAL,
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.target.alt", subject="target", relation="is", object="false",
        risk=KnowledgeRisk.HIGH, evidence_ids=("competitor-e",),
    ))
    gate = TruthAssuranceGate()
    certificate = gate.close_live(
        claim_id="claim.target", knowledge=knowledge, evidence=evidence, verification=verification,
    )
    assert not certificate.closed
    assert any("conflict" in reason for reason in certificate.reasons)


def test_a8_supported_competitor_for_ancestor_blocks_descendant_closure():
    knowledge, evidence, verification = _build_derived_target()
    evidence.record(_evidence(
        "parent-alt-e", subject_id="claim.parent.alt", source_id="parent-alt-source",
        source_family="parent-alt-family", channel=EvidenceChannel.ADVERSARIAL,
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.parent.alt", subject="parent", relation="state", object="invalid",
        risk=KnowledgeRisk.STANDARD, evidence_ids=("parent-alt-e",),
    ))

    snapshot = EpistemicJudge().snapshot(knowledge=knowledge, evidence=evidence)
    assert snapshot.assessment("claim.parent").disposition is EpistemicDisposition.SUPPORTED
    assert snapshot.assessment("claim.child").disposition is EpistemicDisposition.SUPPORTED
    assert any("claim.parent" in row.claim_ids for row in snapshot.contradictions)

    gate = TruthAssuranceGate()
    certificate = gate.close_live(
        claim_id="claim.child", knowledge=knowledge, evidence=evidence, verification=verification,
    )
    assert not certificate.closed
    assert "epistemic_lineage_conflicted" in certificate.reasons


def test_a8_dependency_scope_is_fixed_point_and_order_independent():
    knowledge_a, evidence_a, _ = _build_derived_target()
    evidence_a.record(_evidence(
        "parent-alt-e", subject_id="claim.parent.alt", source_id="parent-alt-source",
        source_family="parent-alt-family", channel=EvidenceChannel.ADVERSARIAL,
    ))
    knowledge_a.add(KnowledgeClaim.create(
        claim_id="claim.parent.alt", subject="parent", relation="state", object="invalid",
        evidence_ids=("parent-alt-e",),
    ))

    evidence_b = EvidenceLedger.from_state(copy.deepcopy(evidence_a.to_state()))
    knowledge_state = copy.deepcopy(knowledge_a.to_state())
    knowledge_state["claims"] = list(reversed(knowledge_state["claims"]))
    knowledge_b = KnowledgeLedger.from_state(knowledge_state)

    judge = EpistemicJudge()
    scope_a = judge.dependency_scope("claim.child", knowledge=knowledge_a, evidence=evidence_a)
    scope_b = judge.dependency_scope("claim.child", knowledge=knowledge_b, evidence=evidence_b)

    assert scope_a.lineage_claim_ids == ("claim.child", "claim.parent")
    assert set(scope_a.scope_claim_ids) == {"claim.child", "claim.parent", "claim.parent.alt"}
    assert scope_a.digest == scope_b.digest


def test_a8_different_dependency_graphs_have_different_scope_identity():
    knowledge_a, evidence_a, _ = _build_derived_target()
    scope_a = EpistemicJudge().dependency_scope("claim.child", knowledge=knowledge_a, evidence=evidence_a)

    evidence_b = EvidenceLedger.from_state(copy.deepcopy(evidence_a.to_state()))
    knowledge_b = KnowledgeLedger()
    knowledge_b.add(knowledge_a.get("claim.parent"))
    knowledge_b.add(KnowledgeClaim.create(
        claim_id="claim.middle", subject="middle", relation="depends", object="parent",
        evidence_ids=(), parent_claim_ids=("claim.parent",),
    ))
    child = knowledge_a.get("claim.child")
    knowledge_b.add(KnowledgeClaim.create(
        claim_id=child.claim_id, subject=child.subject, relation=child.relation, object=child.object,
        risk=child.risk, evidence_ids=child.evidence_ids, parent_claim_ids=("claim.middle",),
    ))
    scope_b = EpistemicJudge().dependency_scope("claim.child", knowledge=knowledge_b, evidence=evidence_b)

    assert scope_a.digest != scope_b.digest


def test_a8_forged_or_omitted_scope_state_fails_live_validation():
    knowledge, evidence, _ = _build_derived_target()
    judge = EpistemicJudge()
    scope = judge.dependency_scope("claim.child", knowledge=knowledge, evidence=evidence)
    state = copy.deepcopy(scope.to_state())
    state["lineage_claim_ids"] = ["claim.child"]
    state["digest"] = type(scope).create_from_state_payload(state).digest
    forged = type(scope).from_state(state)
    assert not judge.validate_dependency_scope(forged, knowledge=knowledge, evidence=evidence)


def test_a8_cross_subject_evidence_remains_non_supporting_inside_scope():
    evidence = EvidenceLedger()
    evidence.record(_evidence(
        "wrong-e", subject_id="claim.someone-else", source_id="source", source_family="family",
        channel=EvidenceChannel.TEST,
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.target", subject="target", relation="is", object="true",
        risk=KnowledgeRisk.STANDARD, evidence_ids=("wrong-e",),
    ))
    judge = EpistemicJudge()
    scope = judge.dependency_scope("claim.target", knowledge=knowledge, evidence=evidence)
    assert scope.assessment("claim.target").disposition is EpistemicDisposition.UNKNOWN
    assert any(row.claim_id == "claim.target" and row.reason == "evidence_subject_mismatch" for row in scope.debts)


def test_a8_negative_current_scope_verification_blocks_closure():
    knowledge, evidence, verification = _build_high_risk_target()
    _record_current_receipt(
        verification, receipt_id="target-negative", claim_id="claim.target", verifier_id="runner-a",
        source_family="family-a", channel=EvidenceChannel.TEST, passed=False,
        evidence_ids=("target-e1",), knowledge=knowledge, evidence=evidence,
    )
    certificate = TruthAssuranceGate().close_live(
        claim_id="claim.target", knowledge=knowledge, evidence=evidence, verification=verification,
    )
    assert not certificate.closed
    assert "negative_verification" in certificate.reasons


def test_a8_v1_snapshot_certificate_remains_global_and_conservatively_stales():
    knowledge, evidence, verification = _build_high_risk_target()
    snapshot = EpistemicJudge().snapshot(knowledge=knowledge, evidence=evidence)
    gate = TruthAssuranceGate()
    certificate = gate.close_snapshot(
        claim_id="claim.target", knowledge=knowledge, evidence=evidence,
        epistemic=snapshot, verification=verification,
    )
    assert certificate.closed

    evidence.record(_evidence(
        "unrelated-e", subject_id="claim.unrelated", source_id="unrelated-source",
        source_family="unrelated-family", channel=EvidenceChannel.OBSERVATION,
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.unrelated", subject="elsewhere", relation="is", object="irrelevant",
        risk=KnowledgeRisk.LOW, evidence_ids=("unrelated-e",),
    ))
    assert not gate.validate_certificate(
        certificate, knowledge=knowledge, evidence=evidence, verification=verification,
    )
