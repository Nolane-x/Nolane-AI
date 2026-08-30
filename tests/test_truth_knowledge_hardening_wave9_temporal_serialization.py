from __future__ import annotations

import copy

import pytest

from nolane.external_core.assurance_truth import TruthClosureCertificate
from nolane.external_core.evidence_truth import EvidenceChannel, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeRisk
from nolane.external_core.verification_truth import TruthVerificationReceipt


T0 = "2025-01-01T00:00:00Z"
T1 = "2030-01-01T00:00:00Z"


def test_a9_legacy_evidence_state_shape_remains_temporal_key_free():
    row = TruthEvidence.create(
        evidence_id="e1",
        subject_id="claim.alpha",
        source_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        polarity=EvidencePolarity.SUPPORT,
        payload_digest="payload:e1",
    )
    state = row.to_state()
    assert "valid_from" not in state
    assert "valid_until" not in state
    assert "temporal_mode" not in state
    assert TruthEvidence.from_state(state) == row


def test_a9_temporal_evidence_state_round_trips_without_changing_legacy_shape():
    row = TruthEvidence.create(
        evidence_id="e1",
        subject_id="claim.alpha",
        source_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        polarity=EvidencePolarity.SUPPORT,
        payload_digest="payload:e1",
        valid_from=T0,
        valid_until=T1,
    )
    state = row.to_state()
    assert state["temporal_mode"] == "validity-interval-v1"
    assert state["valid_from"] == T0
    assert state["valid_until"] == T1
    assert TruthEvidence.from_state(copy.deepcopy(state)) == row


def test_a9_legacy_knowledge_claim_state_shape_remains_temporal_key_free():
    row = KnowledgeClaim.create(
        claim_id="claim.alpha",
        subject="alpha",
        relation="state",
        object="valid",
        risk=KnowledgeRisk.STANDARD,
        evidence_ids=("e1",),
    )
    state = row.to_state()
    assert "valid_from" not in state
    assert "valid_until" not in state
    assert "temporal_mode" not in state
    assert KnowledgeClaim.from_state(state) == row


def test_a9_temporal_claim_state_round_trips_without_changing_legacy_shape():
    row = KnowledgeClaim.create(
        claim_id="claim.alpha",
        subject="alpha",
        relation="state",
        object="valid",
        risk=KnowledgeRisk.STANDARD,
        evidence_ids=("e1",),
        valid_from=T0,
        valid_until=T1,
    )
    state = row.to_state()
    assert state["temporal_mode"] == "validity-interval-v1"
    assert state["valid_from"] == T0
    assert state["valid_until"] == T1
    assert KnowledgeClaim.from_state(copy.deepcopy(state)) == row


def test_a9_temporal_receipt_state_is_v3_and_rejects_global_mixing():
    row = TruthVerificationReceipt.create(
        receipt_id="v3",
        claim_id="claim.alpha",
        verifier_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest="scope",
        temporal_context_digest="time",
        as_of=T0,
        evidence_ids=("e1",),
    )
    state = row.to_state()
    assert state["binding_mode"] == "dependency-scope-temporal-v3"
    assert state["scope_digest"] == "scope"
    assert state["temporal_context_digest"] == "time"
    assert state["as_of"] == T0
    assert "knowledge_digest" not in state
    assert "epistemic_digest" not in state
    assert TruthVerificationReceipt.from_state(copy.deepcopy(state)) == row

    forged = copy.deepcopy(state)
    forged["knowledge_digest"] = "global"
    with pytest.raises(ValueError, match="global|mixed|binding"):
        TruthVerificationReceipt.from_state(forged)


def test_a9_v1_and_v2_verification_state_shapes_remain_temporal_key_free():
    v1 = TruthVerificationReceipt.create(
        receipt_id="v1",
        claim_id="claim.alpha",
        verifier_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        passed=True,
        knowledge_digest="knowledge",
        epistemic_digest="epistemic",
        evidence_ids=("e1",),
    ).to_state()
    v2 = TruthVerificationReceipt.create(
        receipt_id="v2",
        claim_id="claim.alpha",
        verifier_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest="scope",
        evidence_ids=("e1",),
    ).to_state()
    for state in (v1, v2):
        assert "temporal_context_digest" not in state
        assert "as_of" not in state


def test_a9_temporal_certificate_state_is_v3_and_rejects_global_mixing():
    row = TruthClosureCertificate.create(
        claim_id="claim.alpha",
        risk=KnowledgeRisk.STANDARD,
        binding_mode="dependency-scope-temporal-v3",
        scope_digest="scope",
        verification_scope_digest="verification-scope",
        temporal_context_digest="time",
        as_of=T0,
        verification_receipt_ids=("v3",),
        epistemic_debt_ids=(),
        closed=True,
        reasons=(),
    )
    state = row.to_state()
    assert state["binding_mode"] == "dependency-scope-temporal-v3"
    assert state["temporal_context_digest"] == "time"
    assert state["as_of"] == T0
    assert "knowledge_digest" not in state
    assert "evidence_digest" not in state
    assert "epistemic_digest" not in state
    assert TruthClosureCertificate.from_state(copy.deepcopy(state)) == row

    forged = copy.deepcopy(state)
    forged["evidence_digest"] = "global"
    with pytest.raises(ValueError, match="global|mixed|binding"):
        TruthClosureCertificate.from_state(forged)


def test_a9_v1_and_v2_certificate_state_shapes_remain_temporal_key_free():
    v1 = TruthClosureCertificate.create(
        claim_id="claim.alpha",
        risk=KnowledgeRisk.STANDARD,
        knowledge_digest="k",
        evidence_digest="e",
        epistemic_digest="p",
        verification_digest="v",
        verification_receipt_ids=("v1",),
        epistemic_debt_ids=(),
        closed=True,
        reasons=(),
    ).to_state()
    v2 = TruthClosureCertificate.create(
        claim_id="claim.alpha",
        risk=KnowledgeRisk.STANDARD,
        binding_mode="dependency-scope-v2",
        scope_digest="scope",
        verification_scope_digest="verification",
        verification_receipt_ids=("v2",),
        epistemic_debt_ids=(),
        closed=True,
        reasons=(),
    ).to_state()
    for state in (v1, v2):
        assert "temporal_context_digest" not in state
        assert "as_of" not in state
