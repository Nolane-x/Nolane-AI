from __future__ import annotations

import copy
import importlib
from types import SimpleNamespace

import pytest

from nolane.external_core.assurance_truth import TruthClosureCertificate
from nolane.external_core.evidence_truth import EvidenceChannel, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeRisk
from nolane.external_core.verification_truth import TruthVerificationReceipt


T0 = "2025-01-01T00:00:00Z"
T1 = "2030-01-01T00:00:00Z"


def _a9():
    return SimpleNamespace(
        temporal=importlib.import_module("nolane.external_core.temporal_truth"),
        evidence=importlib.import_module("nolane.external_core.evidence_temporal_truth"),
        knowledge=importlib.import_module("nolane.external_core.knowledge_temporal_truth"),
        epistemic=importlib.import_module("nolane.external_core.epistemic_temporal_truth"),
        verification=importlib.import_module("nolane.external_core.verification_temporal_truth"),
        assurance=importlib.import_module("nolane.external_core.assurance_temporal_truth"),
    )


def test_a9_sidecars_do_not_declare_component_authority():
    mods = _a9()
    for module in (
        mods.temporal, mods.evidence, mods.knowledge,
        mods.epistemic, mods.verification, mods.assurance,
    ):
        assert not hasattr(module, "COMPONENT_ID")


def test_a9_legacy_evidence_and_knowledge_shapes_remain_temporal_key_free():
    evidence = TruthEvidence.create(
        evidence_id="e1", subject_id="claim.alpha", source_id="runner", source_family="family",
        channel=EvidenceChannel.TEST, polarity=EvidencePolarity.SUPPORT, payload_digest="payload:e1",
    )
    claim = KnowledgeClaim.create(
        claim_id="claim.alpha", subject="alpha", relation="state", object="valid",
        risk=KnowledgeRisk.STANDARD, evidence_ids=("e1",),
    )
    for state in (evidence.to_state(), claim.to_state()):
        assert "valid_from" not in state
        assert "valid_until" not in state
        assert "temporal_mode" not in state


def test_a9_legacy_v1_v2_verification_and_assurance_shapes_remain_temporal_key_free():
    v1 = TruthVerificationReceipt.create(
        receipt_id="v1", claim_id="claim.alpha", verifier_id="runner", source_family="family",
        channel=EvidenceChannel.TEST, passed=True,
        knowledge_digest="knowledge", epistemic_digest="epistemic", evidence_ids=("e1",),
    ).to_state()
    v2 = TruthVerificationReceipt.create(
        receipt_id="v2", claim_id="claim.alpha", verifier_id="runner", source_family="family",
        channel=EvidenceChannel.TEST, passed=True, scope_digest="scope", evidence_ids=("e1",),
    ).to_state()
    c1 = TruthClosureCertificate.create(
        claim_id="claim.alpha", risk=KnowledgeRisk.STANDARD,
        knowledge_digest="k", evidence_digest="e", epistemic_digest="p", verification_digest="v",
        verification_receipt_ids=("v1",), epistemic_debt_ids=(), closed=True, reasons=(),
    ).to_state()
    c2 = TruthClosureCertificate.create(
        claim_id="claim.alpha", risk=KnowledgeRisk.STANDARD,
        binding_mode="dependency-scope-v2", scope_digest="scope", verification_scope_digest="verification",
        verification_receipt_ids=("v2",), epistemic_debt_ids=(), closed=True, reasons=(),
    ).to_state()
    for state in (v1, v2, c1, c2):
        assert "temporal_context_digest" not in state
        assert "as_of" not in state


def test_a9_interval_and_context_round_trip_with_digest_validation():
    mods = _a9()
    interval = mods.temporal.TruthInterval.create(valid_from=T0, valid_until=T1)
    context = mods.temporal.TemporalContext.create(as_of=T0)
    assert mods.temporal.TruthInterval.from_state(copy.deepcopy(interval.to_state())) == interval
    assert mods.temporal.TemporalContext.from_state(copy.deepcopy(context.to_state())) == context

    forged = copy.deepcopy(interval.to_state())
    forged["valid_until"] = "2031-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="digest"):
        mods.temporal.TruthInterval.from_state(forged)


def test_a9_evidence_and_knowledge_temporal_bindings_round_trip():
    mods = _a9()
    evidence = TruthEvidence.create(
        evidence_id="e1", subject_id="claim.alpha", source_id="runner", source_family="family",
        channel=EvidenceChannel.TEST, polarity=EvidencePolarity.SUPPORT, payload_digest="payload:e1",
    )
    claim = KnowledgeClaim.create(
        claim_id="claim.alpha", subject="alpha", relation="state", object="valid",
        evidence_ids=("e1",),
    )
    evidence_binding = mods.evidence.EvidenceTemporalBinding.create(
        evidence, valid_from=T0, valid_until=T1,
    )
    claim_binding = mods.knowledge.KnowledgeTemporalBinding.create(
        claim, valid_from=T0, valid_until=T1,
    )
    assert mods.evidence.EvidenceTemporalBinding.from_state(evidence_binding.to_state()) == evidence_binding
    assert mods.knowledge.KnowledgeTemporalBinding.from_state(claim_binding.to_state()) == claim_binding


def test_a9_temporal_receipt_state_is_v3_and_global_keys_are_impossible():
    mods = _a9()
    row = mods.verification.TemporalTruthVerificationReceipt.create(
        receipt_id="v3", claim_id="claim.alpha", verifier_id="runner", source_family="family",
        channel=EvidenceChannel.TEST, passed=True,
        scope_digest="scope", temporal_context_digest="time", as_of=T0, evidence_ids=("e1",),
    )
    state = row.to_state()
    assert state["binding_mode"] == "dependency-scope-temporal-v3"
    assert state["temporal_context_digest"] == "time"
    assert state["as_of"] == T0
    assert "knowledge_digest" not in state and "epistemic_digest" not in state
    assert mods.verification.TemporalTruthVerificationReceipt.from_state(copy.deepcopy(state)) == row

    forged = copy.deepcopy(state)
    forged["knowledge_digest"] = "global"
    with pytest.raises(ValueError, match="global|binding|unexpected"):
        mods.verification.TemporalTruthVerificationReceipt.from_state(forged)


def test_a9_temporal_certificate_state_is_v3_and_global_keys_are_impossible():
    mods = _a9()
    row = mods.assurance.TemporalTruthClosureCertificate.create(
        claim_id="claim.alpha", risk=KnowledgeRisk.STANDARD,
        scope_digest="scope", verification_scope_digest="verification",
        temporal_context_digest="time", as_of=T0,
        verification_receipt_ids=("v3",), epistemic_debt_ids=(),
        closed=True, reasons=(),
    )
    state = row.to_state()
    assert state["binding_mode"] == "dependency-scope-temporal-v3"
    assert state["temporal_context_digest"] == "time"
    assert state["as_of"] == T0
    assert "knowledge_digest" not in state and "evidence_digest" not in state
    assert mods.assurance.TemporalTruthClosureCertificate.from_state(copy.deepcopy(state)) == row

    forged = copy.deepcopy(state)
    forged["evidence_digest"] = "global"
    with pytest.raises(ValueError, match="global|binding|unexpected"):
        mods.assurance.TemporalTruthClosureCertificate.from_state(forged)
