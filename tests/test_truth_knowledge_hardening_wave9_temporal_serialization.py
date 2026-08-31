from __future__ import annotations

import copy
import importlib
from types import SimpleNamespace

import pytest

from nolane.external_core.assurance_truth import TruthClosureCertificate
from nolane.external_core.evidence_truth import EvidenceChannel, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.verification_truth import RELATION_SCOPED_BINDING_MODE, TruthVerificationReceipt
from nolane.memory.knowledge import RelationCardinality, RelationSemanticsRegistry, RelationSemanticsRevision


T0 = "2025-01-01T00:00:00Z"
T1 = "2030-01-01T00:00:00Z"
TEMPORAL_V4 = "relation-aware-temporal-v4"


def _a9():
    return SimpleNamespace(
        temporal=importlib.import_module("nolane.external_core.temporal_truth"),
        evidence=importlib.import_module("nolane.external_core.evidence_temporal_truth"),
        knowledge=importlib.import_module("nolane.external_core.knowledge_temporal_truth"),
        epistemic=importlib.import_module("nolane.external_core.epistemic_temporal_truth"),
        verification=importlib.import_module("nolane.external_core.verification_temporal_truth"),
        assurance=importlib.import_module("nolane.external_core.assurance_temporal_truth"),
    )


def _evidence() -> TruthEvidence:
    return TruthEvidence.create(
        evidence_id="e1",
        subject_id="claim.alpha",
        source_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        polarity=EvidencePolarity.SUPPORT,
        payload_digest="payload:e1",
    )


def _claim() -> KnowledgeClaim:
    return KnowledgeClaim.create(
        claim_id="claim.alpha",
        subject="alpha",
        relation="state",
        object="valid",
        risk=KnowledgeRisk.STANDARD,
        evidence_ids=("e1",),
    )


def _relations() -> RelationSemanticsRegistry:
    registry = RelationSemanticsRegistry()
    registry.record(RelationSemanticsRevision.create(
        relation="state",
        revision=1,
        cardinality=RelationCardinality.EXCLUSIVE,
    ))
    return registry


def test_a9_sidecars_do_not_declare_component_authority():
    mods = _a9()
    for module in (
        mods.temporal,
        mods.evidence,
        mods.knowledge,
        mods.epistemic,
        mods.verification,
        mods.assurance,
    ):
        assert not hasattr(module, "COMPONENT_ID")


def test_a9_legacy_a1_a10_shapes_remain_temporal_key_free():
    evidence = _evidence().to_state()
    claim = _claim().to_state()
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
        scope_digest="scope-v2",
        evidence_ids=("e1",),
    ).to_state()
    v3 = TruthVerificationReceipt.create(
        receipt_id="v3",
        claim_id="claim.alpha",
        verifier_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        passed=True,
        binding_mode=RELATION_SCOPED_BINDING_MODE,
        scope_digest="scope-v3",
        evidence_ids=("e1",),
    ).to_state()
    c1 = TruthClosureCertificate.create(
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
    c2 = TruthClosureCertificate.create(
        claim_id="claim.alpha",
        risk=KnowledgeRisk.STANDARD,
        binding_mode="dependency-scope-v2",
        scope_digest="scope-v2",
        verification_scope_digest="verification-v2",
        verification_receipt_ids=("v2",),
        epistemic_debt_ids=(),
        closed=True,
        reasons=(),
    ).to_state()
    c3 = TruthClosureCertificate.create(
        claim_id="claim.alpha",
        risk=KnowledgeRisk.STANDARD,
        binding_mode=RELATION_SCOPED_BINDING_MODE,
        scope_digest="scope-v3",
        verification_scope_digest="verification-v3",
        verification_receipt_ids=("v3",),
        epistemic_debt_ids=(),
        closed=True,
        reasons=(),
    ).to_state()
    for state in (evidence, claim, v1, v2, v3, c1, c2, c3):
        assert "temporal_context_digest" not in state
        assert "as_of" not in state
        assert "valid_from" not in state
        assert "valid_until" not in state


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


def test_a9_evidence_and_knowledge_temporal_bindings_round_trip_and_rebind_fail_closed():
    mods = _a9()
    evidence = _evidence()
    claim = _claim()
    evidence_binding = mods.evidence.EvidenceTemporalBinding.create(
        evidence,
        valid_from=T0,
        valid_until=T1,
    )
    claim_binding = mods.knowledge.KnowledgeTemporalBinding.create(
        claim,
        valid_from=T0,
        valid_until=T1,
    )
    assert mods.evidence.EvidenceTemporalBinding.from_state(evidence_binding.to_state()) == evidence_binding
    assert mods.knowledge.KnowledgeTemporalBinding.from_state(claim_binding.to_state()) == claim_binding

    evidence_view = mods.evidence.TemporalEvidenceView()
    evidence_view.record(evidence_binding)
    with pytest.raises(ValueError, match="rebind|collision"):
        evidence_view.bind(evidence, valid_from=T0, valid_until=None)

    knowledge_view = mods.knowledge.TemporalKnowledgeView()
    knowledge_view.record(claim_binding)
    with pytest.raises(ValueError, match="rebind|collision"):
        knowledge_view.bind(claim, valid_from=T0, valid_until=None)


def test_a9_temporal_scope_round_trip_is_tamper_evident_and_not_self_authenticating():
    mods = _a9()
    from nolane.external_core.evidence_truth import EvidenceLedger

    evidence_ledger = EvidenceLedger()
    evidence_ledger.record(_evidence())
    knowledge = KnowledgeLedger()
    knowledge.add(_claim())
    context = mods.temporal.TemporalContext.create(as_of=T0)
    evidence_temporal = mods.evidence.TemporalEvidenceView()
    knowledge_temporal = mods.knowledge.TemporalKnowledgeView()
    judge = mods.epistemic.TemporalEpistemicJudge()
    scope = judge.relation_aware_dependency_scope(
        "claim.alpha",
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence_ledger,
        relation_semantics=_relations(),
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )
    restored = mods.epistemic.TemporalTruthRelationAwareScope.from_state(copy.deepcopy(scope.to_state()))
    assert restored == scope

    forged_state = copy.deepcopy(scope.to_state())
    forged_state["scope_claim_ids"] = []
    with pytest.raises(ValueError):
        mods.epistemic.TemporalTruthRelationAwareScope.from_state(forged_state)


def test_a9_temporal_receipt_state_is_v4_and_v1_v3_keys_are_impossible():
    mods = _a9()
    row = mods.verification.TemporalTruthVerificationReceipt.create(
        receipt_id="v4",
        claim_id="claim.alpha",
        verifier_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest="scope-v4",
        temporal_context_digest="time",
        as_of=T0,
        evidence_ids=("e1",),
    )
    state = row.to_state()
    assert state["binding_mode"] == TEMPORAL_V4
    assert state["temporal_context_digest"] == "time"
    assert state["as_of"] == T0
    assert "knowledge_digest" not in state and "epistemic_digest" not in state
    assert mods.verification.TemporalTruthVerificationReceipt.from_state(copy.deepcopy(state)) == row

    for key in ("knowledge_digest", "epistemic_digest", "relation_semantics_digest"):
        forged = copy.deepcopy(state)
        forged[key] = "forged"
        with pytest.raises(ValueError, match="binding|unexpected|global|relation"):
            mods.verification.TemporalTruthVerificationReceipt.from_state(forged)


def test_a9_temporal_certificate_state_is_v4_and_global_keys_are_impossible():
    mods = _a9()
    row = mods.assurance.TemporalTruthClosureCertificate.create(
        claim_id="claim.alpha",
        risk=KnowledgeRisk.STANDARD,
        scope_digest="scope-v4",
        verification_scope_digest="verification-v4",
        temporal_context_digest="time",
        as_of=T0,
        verification_receipt_ids=("v4",),
        epistemic_debt_ids=(),
        closed=True,
        reasons=(),
    )
    state = row.to_state()
    assert state["binding_mode"] == TEMPORAL_V4
    assert state["temporal_context_digest"] == "time"
    assert state["as_of"] == T0
    assert "knowledge_digest" not in state and "evidence_digest" not in state
    assert mods.assurance.TemporalTruthClosureCertificate.from_state(copy.deepcopy(state)) == row

    for key in ("knowledge_digest", "evidence_digest", "epistemic_digest"):
        forged = copy.deepcopy(state)
        forged[key] = "global"
        with pytest.raises(ValueError, match="binding|unexpected|global"):
            mods.assurance.TemporalTruthClosureCertificate.from_state(forged)
