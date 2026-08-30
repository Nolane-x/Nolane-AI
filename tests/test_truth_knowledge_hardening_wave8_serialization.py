from __future__ import annotations

import copy

import pytest

from nolane.external_core.assurance_truth import TruthAssuranceGate, TruthClosureCertificate
from nolane.external_core.epistemic_truth import EpistemicJudge, TruthDependencyScope
from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.verification_truth import TruthVerificationLedger, TruthVerificationReceipt


def _base_scope():
    evidence = EvidenceLedger()
    evidence.record(TruthEvidence.create(
        evidence_id="e1", subject_id="claim.alpha", source_id="runner",
        source_family="family", channel=EvidenceChannel.TEST,
        polarity=EvidencePolarity.SUPPORT, payload_digest="payload:e1",
    ))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.alpha", subject="alpha", relation="is", object="true",
        risk=KnowledgeRisk.STANDARD, evidence_ids=("e1",),
    ))
    scope = EpistemicJudge().dependency_scope("claim.alpha", knowledge=knowledge, evidence=evidence)
    return knowledge, evidence, scope


def test_a8_v1_verification_state_shape_remains_legacy_exact():
    row = TruthVerificationReceipt.create(
        receipt_id="v1", claim_id="claim.alpha", verifier_id="runner",
        source_family="family", channel=EvidenceChannel.TEST, passed=True,
        knowledge_digest="knowledge", epistemic_digest="epistemic", evidence_ids=("e1",),
    )
    state = row.to_state()
    assert "binding_mode" not in state
    assert "scope_digest" not in state
    assert state["knowledge_digest"] == "knowledge"
    assert state["epistemic_digest"] == "epistemic"
    assert TruthVerificationReceipt.from_state(state) == row


def test_a8_scoped_verification_state_rejects_mixed_global_bindings():
    _, _, scope = _base_scope()
    row = TruthVerificationReceipt.create(
        receipt_id="v2", claim_id="claim.alpha", verifier_id="runner",
        source_family="family", channel=EvidenceChannel.TEST, passed=True,
        scope_digest=scope.digest, evidence_ids=("e1",),
    )
    state = row.to_state()
    state["knowledge_digest"] = "forged-global"
    with pytest.raises(ValueError, match="cannot contain global bindings"):
        TruthVerificationReceipt.from_state(state)


def test_a8_v1_certificate_state_shape_remains_legacy_exact():
    row = TruthClosureCertificate.create(
        claim_id="claim.alpha", risk=KnowledgeRisk.STANDARD,
        knowledge_digest="k", evidence_digest="e", epistemic_digest="p", verification_digest="v",
        verification_receipt_ids=("v1",), epistemic_debt_ids=(), closed=True, reasons=(),
    )
    state = row.to_state()
    assert "binding_mode" not in state
    assert "scope_digest" not in state
    assert "verification_scope_digest" not in state
    assert TruthClosureCertificate.from_state(state) == row


def test_a8_scoped_certificate_state_rejects_mixed_global_bindings():
    _, _, scope = _base_scope()
    row = TruthClosureCertificate.create(
        claim_id="claim.alpha", risk=KnowledgeRisk.STANDARD,
        binding_mode="dependency-scope-v2", scope_digest=scope.digest,
        verification_scope_digest="scoped-verification",
        verification_receipt_ids=("v2",), epistemic_debt_ids=(), closed=True, reasons=(),
    )
    state = row.to_state()
    state["evidence_digest"] = "forged-global"
    with pytest.raises(ValueError, match="cannot contain global bindings"):
        TruthClosureCertificate.from_state(state)


def test_a8_content_valid_but_omitted_evidence_scope_fails_live_authority_validation():
    knowledge, evidence, scope = _base_scope()
    state = copy.deepcopy(scope.to_state())
    state["evidence_ids"] = []
    state["digest"] = TruthDependencyScope.create_from_state_payload(state).digest
    forged = TruthDependencyScope.from_state(state)
    assert not EpistemicJudge().validate_dependency_scope(forged, knowledge=knowledge, evidence=evidence)


def test_a8_scoped_certificate_requires_live_revalidation_not_digest_only():
    knowledge, evidence, scope = _base_scope()
    verification = TruthVerificationLedger()
    verification.record(TruthVerificationReceipt.create(
        receipt_id="v2", claim_id="claim.alpha", verifier_id="runner",
        source_family="family", channel=EvidenceChannel.TEST, passed=True,
        scope_digest=scope.digest, evidence_ids=("e1",),
    ))
    gate = TruthAssuranceGate()
    certificate = gate.close_live(
        claim_id="claim.alpha", knowledge=knowledge, evidence=evidence, verification=verification,
    )
    assert certificate.closed and certificate.is_scoped
    restored = TruthClosureCertificate.from_state(certificate.to_state())
    assert restored == certificate
    evidence.revoke("e1", reason="withdrawn")
    assert not gate.validate_certificate(
        restored, knowledge=knowledge, evidence=evidence, verification=verification,
    )
