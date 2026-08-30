from __future__ import annotations

import importlib

import pytest

from nolane.external_core.assurance_truth import TruthAssuranceGate
from nolane.external_core.epistemic_truth import EpistemicDisposition, EpistemicJudge
from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.verification_truth import TruthVerificationLedger, TruthVerificationReceipt


T_2020 = "2020-01-01T00:00:00Z"
T_2025 = "2025-01-01T00:00:00Z"
T_2030 = "2030-01-01T00:00:00Z"


def _temporal_module():
    return importlib.import_module("nolane.external_core.temporal_truth")


def _context(as_of: str):
    return _temporal_module().TemporalContext.create(as_of=as_of)


def _temporal_evidence(
    evidence_id: str,
    *,
    subject_id: str,
    source_id: str,
    source_family: str,
    channel: EvidenceChannel,
    valid_from: str | None = None,
    valid_until: str | None = None,
) -> TruthEvidence:
    return TruthEvidence.create(
        evidence_id=evidence_id,
        subject_id=subject_id,
        source_id=source_id,
        source_family=source_family,
        channel=channel,
        polarity=EvidencePolarity.SUPPORT,
        payload_digest=f"payload:{evidence_id}",
        valid_from=valid_from,
        valid_until=valid_until,
    )


def _temporal_claim(
    claim_id: str,
    *,
    subject: str,
    relation: str,
    object_: str,
    evidence_ids: tuple[str, ...],
    valid_from: str | None = None,
    valid_until: str | None = None,
    parent_claim_ids: tuple[str, ...] = (),
) -> KnowledgeClaim:
    return KnowledgeClaim.create(
        claim_id=claim_id,
        subject=subject,
        relation=relation,
        object=object_,
        risk=KnowledgeRisk.STANDARD,
        evidence_ids=evidence_ids,
        parent_claim_ids=parent_claim_ids,
        valid_from=valid_from,
        valid_until=valid_until,
    )


def _record_temporal_receipt(
    verification: TruthVerificationLedger,
    *,
    receipt_id: str,
    claim_id: str,
    evidence_id: str,
    knowledge: KnowledgeLedger,
    evidence: EvidenceLedger,
    context,
) -> TruthVerificationReceipt:
    scope = EpistemicJudge().temporal_dependency_scope(
        claim_id,
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
    )
    receipt = TruthVerificationReceipt.create(
        receipt_id=receipt_id,
        claim_id=claim_id,
        verifier_id=f"verifier:{receipt_id}",
        source_family=f"family:{receipt_id}",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest=scope.digest,
        temporal_context_digest=context.digest,
        as_of=context.as_of,
        evidence_ids=(evidence_id,),
    )
    verification.record(receipt)
    return receipt


def test_a9_temporal_context_is_explicit_canonical_and_content_addressed():
    module = _temporal_module()
    context_a = module.TemporalContext.create(as_of=T_2025)
    context_b = module.TemporalContext.from_state(context_a.to_state())

    assert context_a == context_b
    assert context_a.as_of == T_2025
    assert context_a.digest == context_b.digest
    assert not hasattr(module, "COMPONENT_ID")

    for malformed in (
        "2025-01-01T00:00:00",
        "2025-01-01T00:00:00+00:00",
        "2025-01-01T00:00:00.000Z",
        " 2025-01-01T00:00:00Z",
        "2025-13-01T00:00:00Z",
    ):
        with pytest.raises(ValueError):
            module.TemporalContext.create(as_of=malformed)


def test_a9_temporal_evidence_uses_half_open_validity_and_expires_at_upper_bound():
    evidence = EvidenceLedger()
    evidence.record(_temporal_evidence(
        "e-old",
        subject_id="claim.old",
        source_id="source-old",
        source_family="family-old",
        channel=EvidenceChannel.OBSERVATION,
        valid_from=T_2020,
        valid_until=T_2025,
    ))

    before = _context("2024-12-31T23:59:59Z")
    boundary = _context(T_2025)

    assert evidence.state_at("e-old", temporal_context=before) == "active"
    assert evidence.state_at("e-old", temporal_context=boundary) == "expired"


def test_a9_expired_evidence_cannot_support_temporal_claim():
    evidence = EvidenceLedger()
    evidence.record(_temporal_evidence(
        "e",
        subject_id="claim.alpha",
        source_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        valid_from=T_2020,
        valid_until=T_2025,
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(_temporal_claim(
        "claim.alpha",
        subject="alpha",
        relation="state",
        object_="old",
        evidence_ids=("e",),
        valid_from=T_2020,
        valid_until=T_2030,
    ))

    scope = EpistemicJudge().temporal_dependency_scope(
        "claim.alpha",
        temporal_context=_context(T_2025),
        knowledge=knowledge,
        evidence=evidence,
    )

    assert scope.assessment("claim.alpha").disposition is EpistemicDisposition.UNKNOWN
    assert any(row.claim_id == "claim.alpha" and row.reason == "evidence_expired" for row in scope.debts)


def test_a9_non_overlapping_historical_claims_do_not_conflict_at_same_as_of():
    evidence = EvidenceLedger()
    evidence.record(_temporal_evidence(
        "e-old", subject_id="claim.old", source_id="archive-old", source_family="archive",
        channel=EvidenceChannel.OBSERVATION, valid_from=T_2020, valid_until=T_2025,
    ))
    evidence.record(_temporal_evidence(
        "e-new", subject_id="claim.new", source_id="archive-new", source_family="archive-new",
        channel=EvidenceChannel.OBSERVATION, valid_from=T_2025, valid_until=None,
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(_temporal_claim(
        "claim.old", subject="service", relation="status", object_="legacy",
        evidence_ids=("e-old",), valid_from=T_2020, valid_until=T_2025,
    ))
    knowledge.add(_temporal_claim(
        "claim.new", subject="service", relation="status", object_="current",
        evidence_ids=("e-new",), valid_from=T_2025, valid_until=None,
    ))

    scope = EpistemicJudge().temporal_dependency_scope(
        "claim.new", temporal_context=_context(T_2025), knowledge=knowledge, evidence=evidence,
    )

    assert scope.assessment("claim.new").disposition is EpistemicDisposition.SUPPORTED
    assert "claim.old" not in scope.scope_claim_ids
    assert not scope.contradictions


def test_a9_temporal_parent_outside_as_of_fails_descendant_lineage_closed():
    evidence = EvidenceLedger()
    evidence.record(_temporal_evidence(
        "parent-e", subject_id="claim.parent", source_id="parent", source_family="family-parent",
        channel=EvidenceChannel.TEST, valid_from=T_2020, valid_until=T_2025,
    ))
    evidence.record(_temporal_evidence(
        "child-e", subject_id="claim.child", source_id="child", source_family="family-child",
        channel=EvidenceChannel.TEST, valid_from=T_2020, valid_until=T_2030,
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(_temporal_claim(
        "claim.parent", subject="parent", relation="state", object_="valid",
        evidence_ids=("parent-e",), valid_from=T_2020, valid_until=T_2025,
    ))
    knowledge.add(_temporal_claim(
        "claim.child", subject="child", relation="depends", object_="parent",
        evidence_ids=("child-e",), valid_from=T_2020, valid_until=T_2030,
        parent_claim_ids=("claim.parent",),
    ))

    scope = EpistemicJudge().temporal_dependency_scope(
        "claim.child", temporal_context=_context(T_2025), knowledge=knowledge, evidence=evidence,
    )
    assert scope.assessment("claim.child").disposition is not EpistemicDisposition.SUPPORTED
    assert any(row.claim_id == "claim.child" and row.reason == "parent_not_applicable" for row in scope.debts)


def test_a9_verification_receipt_binds_temporal_context_and_rejects_other_as_of():
    evidence = EvidenceLedger()
    evidence.record(_temporal_evidence(
        "e", subject_id="claim.alpha", source_id="runner", source_family="family",
        channel=EvidenceChannel.TEST, valid_from=T_2020, valid_until=T_2030,
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(_temporal_claim(
        "claim.alpha", subject="alpha", relation="state", object_="valid",
        evidence_ids=("e",), valid_from=T_2020, valid_until=T_2030,
    ))
    verification = TruthVerificationLedger()
    at_2025 = _context(T_2025)
    receipt = _record_temporal_receipt(
        verification, receipt_id="v3", claim_id="claim.alpha", evidence_id="e",
        knowledge=knowledge, evidence=evidence, context=at_2025,
    )

    assert receipt.binding_mode == "dependency-scope-temporal-v3"
    assert receipt.temporal_context_digest == at_2025.digest
    assert receipt.as_of == T_2025

    scope_2030 = EpistemicJudge().temporal_dependency_scope(
        "claim.alpha", temporal_context=_context("2029-12-31T23:59:59Z"),
        knowledge=knowledge, evidence=evidence,
    )
    assert receipt.scope_digest != scope_2030.digest or receipt.as_of != "2029-12-31T23:59:59Z"
    assert not verification.receipt_is_current_temporal(
        receipt,
        scope=scope_2030,
        temporal_context=_context("2029-12-31T23:59:59Z"),
    )


def test_a9_assurance_certificate_is_bound_to_explicit_as_of_and_live_temporal_scope():
    evidence = EvidenceLedger()
    evidence.record(_temporal_evidence(
        "e", subject_id="claim.alpha", source_id="runner", source_family="family",
        channel=EvidenceChannel.TEST, valid_from=T_2020, valid_until=T_2030,
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(_temporal_claim(
        "claim.alpha", subject="alpha", relation="state", object_="valid",
        evidence_ids=("e",), valid_from=T_2020, valid_until=T_2030,
    ))
    verification = TruthVerificationLedger()
    at_2025 = _context(T_2025)
    _record_temporal_receipt(
        verification, receipt_id="v3", claim_id="claim.alpha", evidence_id="e",
        knowledge=knowledge, evidence=evidence, context=at_2025,
    )

    gate = TruthAssuranceGate()
    certificate = gate.close_temporal(
        claim_id="claim.alpha",
        temporal_context=at_2025,
        knowledge=knowledge,
        evidence=evidence,
        verification=verification,
    )
    assert certificate.closed
    assert certificate.binding_mode == "dependency-scope-temporal-v3"
    assert certificate.as_of == T_2025
    assert certificate.temporal_context_digest == at_2025.digest

    assert gate.validate_temporal_certificate(
        certificate,
        temporal_context=at_2025,
        knowledge=knowledge,
        evidence=evidence,
        verification=verification,
    )
    assert not gate.validate_temporal_certificate(
        certificate,
        temporal_context=_context("2026-01-01T00:00:00Z"),
        knowledge=knowledge,
        evidence=evidence,
        verification=verification,
    )


def test_a9_temporal_assurance_fails_after_bound_evidence_revocation():
    evidence = EvidenceLedger()
    evidence.record(_temporal_evidence(
        "e", subject_id="claim.alpha", source_id="runner", source_family="family",
        channel=EvidenceChannel.TEST, valid_from=T_2020, valid_until=T_2030,
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(_temporal_claim(
        "claim.alpha", subject="alpha", relation="state", object_="valid",
        evidence_ids=("e",), valid_from=T_2020, valid_until=T_2030,
    ))
    verification = TruthVerificationLedger()
    context = _context(T_2025)
    _record_temporal_receipt(
        verification, receipt_id="v3", claim_id="claim.alpha", evidence_id="e",
        knowledge=knowledge, evidence=evidence, context=context,
    )
    gate = TruthAssuranceGate()
    certificate = gate.close_temporal(
        claim_id="claim.alpha", temporal_context=context,
        knowledge=knowledge, evidence=evidence, verification=verification,
    )
    assert certificate.closed
    evidence.revoke("e", reason="withdrawn")
    assert not gate.validate_temporal_certificate(
        certificate, temporal_context=context,
        knowledge=knowledge, evidence=evidence, verification=verification,
    )
