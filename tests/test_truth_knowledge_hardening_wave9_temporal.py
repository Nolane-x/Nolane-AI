from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.memory.knowledge import RelationCardinality, RelationSemanticsRegistry, RelationSemanticsRevision


T_2020 = "2020-01-01T00:00:00Z"
T_2025 = "2025-01-01T00:00:00Z"
T_2030 = "2030-01-01T00:00:00Z"
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


def _relations(*rows: tuple[str, RelationCardinality]) -> RelationSemanticsRegistry:
    registry = RelationSemanticsRegistry()
    for relation, cardinality in rows:
        registry.record(RelationSemanticsRevision.create(
            relation=relation,
            revision=1,
            cardinality=cardinality,
        ))
    return registry


def _evidence(
    evidence_id: str,
    *,
    claim_id: str,
    source_id: str = "runner",
    source_family: str = "family",
    channel: EvidenceChannel = EvidenceChannel.TEST,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORT,
) -> TruthEvidence:
    return TruthEvidence.create(
        evidence_id=evidence_id,
        subject_id=claim_id,
        source_id=source_id,
        source_family=source_family,
        channel=channel,
        polarity=polarity,
        payload_digest=f"payload:{evidence_id}",
    )


def _claim(
    claim_id: str,
    *,
    subject: str,
    relation: str,
    object_: str,
    evidence_ids: tuple[str, ...],
    parent_claim_ids: tuple[str, ...] = (),
    risk: KnowledgeRisk = KnowledgeRisk.STANDARD,
) -> KnowledgeClaim:
    return KnowledgeClaim.create(
        claim_id=claim_id,
        subject=subject,
        relation=relation,
        object=object_,
        risk=risk,
        evidence_ids=evidence_ids,
        parent_claim_ids=parent_claim_ids,
    )


def _context(mods, as_of: str):
    return mods.temporal.TemporalContext.create(as_of=as_of)


def _scope(
    mods,
    *,
    claim_id: str,
    context,
    knowledge: KnowledgeLedger,
    evidence: EvidenceLedger,
    relations: RelationSemanticsRegistry,
    knowledge_temporal,
    evidence_temporal,
):
    return mods.epistemic.TemporalEpistemicJudge().relation_aware_dependency_scope(
        claim_id,
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=relations,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )


def _record_receipt(
    mods,
    ledger,
    *,
    receipt_id: str,
    claim_id: str,
    evidence_id: str,
    source_id: str,
    source_family: str,
    channel: EvidenceChannel,
    context,
    scope,
    passed: bool = True,
):
    row = mods.verification.TemporalTruthVerificationReceipt.create(
        receipt_id=receipt_id,
        claim_id=claim_id,
        verifier_id=source_id,
        source_family=source_family,
        channel=channel,
        passed=passed,
        scope_digest=scope.digest,
        temporal_context_digest=context.digest,
        as_of=context.as_of,
        evidence_ids=(evidence_id,),
    )
    ledger.record(row)
    return row


def test_a9_context_is_explicit_canonical_content_addressed_and_clock_free():
    mods = _a9()
    context = _context(mods, T_2025)
    assert mods.temporal.TemporalContext.from_state(context.to_state()) == context
    assert context.as_of == T_2025
    assert not hasattr(mods.temporal, "COMPONENT_ID")

    for malformed in (
        "2025-01-01T00:00:00",
        "2025-01-01T00:00:00+00:00",
        "2025-01-01T00:00:00.000Z",
        " 2025-01-01T00:00:00Z",
        "2025-13-01T00:00:00Z",
    ):
        with pytest.raises(ValueError):
            mods.temporal.TemporalContext.create(as_of=malformed)


def test_a9_evidence_interval_is_half_open_and_expired_at_upper_boundary():
    mods = _a9()
    evidence = EvidenceLedger()
    row = _evidence("e-old", claim_id="claim.old")
    evidence.record(row)
    temporal = mods.evidence.TemporalEvidenceView()
    temporal.bind(row, valid_from=T_2020, valid_until=T_2025)

    assert temporal.state_at(
        "e-old",
        evidence=evidence,
        temporal_context=_context(mods, "2024-12-31T23:59:59Z"),
    ) == "active"
    assert temporal.state_at(
        "e-old",
        evidence=evidence,
        temporal_context=_context(mods, T_2025),
    ) == "expired"


def test_a9_expired_evidence_cannot_support_temporal_claim():
    mods = _a9()
    evidence = EvidenceLedger()
    row = _evidence("e", claim_id="claim.alpha")
    evidence.record(row)
    evidence_temporal = mods.evidence.TemporalEvidenceView()
    evidence_temporal.bind(row, valid_from=T_2020, valid_until=T_2025)

    knowledge = KnowledgeLedger()
    claim = _claim("claim.alpha", subject="alpha", relation="state", object_="old", evidence_ids=("e",))
    knowledge.add(claim)
    knowledge_temporal = mods.knowledge.TemporalKnowledgeView()
    knowledge_temporal.bind(claim, valid_from=T_2020, valid_until=T_2030)

    scope = _scope(
        mods,
        claim_id="claim.alpha",
        context=_context(mods, T_2025),
        knowledge=knowledge,
        evidence=evidence,
        relations=_relations(("state", RelationCardinality.EXCLUSIVE)),
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )
    assert scope.assessment("claim.alpha").disposition.value == "unknown"
    assert any(row.claim_id == "claim.alpha" and row.reason == "evidence_expired" for row in scope.debts)


def test_a9_non_overlapping_exclusive_historical_claims_do_not_create_live_conflict():
    mods = _a9()
    evidence = EvidenceLedger()
    old_e = _evidence("e-old", claim_id="claim.old", source_id="old", source_family="old-family")
    new_e = _evidence("e-new", claim_id="claim.new", source_id="new", source_family="new-family")
    evidence.record(old_e)
    evidence.record(new_e)
    evidence_temporal = mods.evidence.TemporalEvidenceView()
    evidence_temporal.bind(old_e, valid_from=T_2020, valid_until=T_2025)
    evidence_temporal.bind(new_e, valid_from=T_2025, valid_until=None)

    knowledge = KnowledgeLedger()
    old = _claim("claim.old", subject="service", relation="status", object_="legacy", evidence_ids=("e-old",))
    new = _claim("claim.new", subject="service", relation="status", object_="current", evidence_ids=("e-new",))
    knowledge.add(old)
    knowledge.add(new)
    knowledge_temporal = mods.knowledge.TemporalKnowledgeView()
    knowledge_temporal.bind(old, valid_from=T_2020, valid_until=T_2025)
    knowledge_temporal.bind(new, valid_from=T_2025, valid_until=None)

    scope = _scope(
        mods,
        claim_id="claim.new",
        context=_context(mods, T_2025),
        knowledge=knowledge,
        evidence=evidence,
        relations=_relations(("status", RelationCardinality.EXCLUSIVE)),
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )
    assert scope.assessment("claim.new").disposition.value == "supported"
    assert "claim.old" not in scope.scope_claim_ids
    assert not scope.contradictions


def test_a9_temporal_scope_preserves_a10_multi_value_and_unspecified_semantics():
    mods = _a9()
    evidence = EvidenceLedger()
    for evidence_id, claim_id, family in (("e-en", "claim.en", "family-en"), ("e-fr", "claim.fr", "family-fr")):
        evidence.record(_evidence(evidence_id, claim_id=claim_id, source_id=family, source_family=family))
    evidence_temporal = mods.evidence.TemporalEvidenceView()

    knowledge = KnowledgeLedger()
    en = _claim("claim.en", subject="alice", relation="speaks", object_="English", evidence_ids=("e-en",))
    fr = _claim("claim.fr", subject="alice", relation="speaks", object_="French", evidence_ids=("e-fr",))
    knowledge.add(en)
    knowledge.add(fr)
    knowledge_temporal = mods.knowledge.TemporalKnowledgeView()

    multi = _scope(
        mods,
        claim_id="claim.en",
        context=_context(mods, T_2025),
        knowledge=knowledge,
        evidence=evidence,
        relations=_relations(("speaks", RelationCardinality.MULTI_VALUED)),
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )
    assert multi.scope_claim_ids == ("claim.en",)
    assert not multi.contradictions

    unspecified = _scope(
        mods,
        claim_id="claim.en",
        context=_context(mods, T_2025),
        knowledge=knowledge,
        evidence=evidence,
        relations=RelationSemanticsRegistry(),
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )
    assert set(unspecified.scope_claim_ids) == {"claim.en", "claim.fr"}
    assert not unspecified.contradictions
    assert any(row.reason == "relation_semantics_unspecified_for_multiple_values" for row in unspecified.debts)


def test_a9_required_parent_outside_window_fails_descendant_closed():
    mods = _a9()
    evidence = EvidenceLedger()
    parent_e = _evidence("parent-e", claim_id="claim.parent", source_id="parent", source_family="parent-family")
    child_e = _evidence("child-e", claim_id="claim.child", source_id="child", source_family="child-family")
    evidence.record(parent_e)
    evidence.record(child_e)
    evidence_temporal = mods.evidence.TemporalEvidenceView()
    evidence_temporal.bind(parent_e, valid_from=T_2020, valid_until=T_2025)
    evidence_temporal.bind(child_e, valid_from=T_2020, valid_until=T_2030)

    knowledge = KnowledgeLedger()
    parent = _claim("claim.parent", subject="parent", relation="state", object_="valid", evidence_ids=("parent-e",))
    knowledge.add(parent)
    child = _claim(
        "claim.child",
        subject="child",
        relation="depends",
        object_="parent",
        evidence_ids=("child-e",),
        parent_claim_ids=("claim.parent",),
    )
    knowledge.add(child)
    knowledge_temporal = mods.knowledge.TemporalKnowledgeView()
    knowledge_temporal.bind(parent, valid_from=T_2020, valid_until=T_2025)
    knowledge_temporal.bind(child, valid_from=T_2020, valid_until=T_2030)

    scope = _scope(
        mods,
        claim_id="claim.child",
        context=_context(mods, T_2025),
        knowledge=knowledge,
        evidence=evidence,
        relations=_relations(
            ("state", RelationCardinality.EXCLUSIVE),
            ("depends", RelationCardinality.EXCLUSIVE),
        ),
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )
    assert scope.assessment("claim.child").disposition.value != "supported"
    assert any(row.claim_id == "claim.child" and row.reason == "parent_not_applicable" for row in scope.debts)


def test_a9_temporal_verification_is_v4_and_bound_to_exact_context_and_scope():
    mods = _a9()
    evidence = EvidenceLedger()
    row = _evidence("e", claim_id="claim.alpha")
    evidence.record(row)
    evidence_temporal = mods.evidence.TemporalEvidenceView()
    evidence_temporal.bind(row, valid_from=T_2020, valid_until=T_2030)

    knowledge = KnowledgeLedger()
    claim = _claim("claim.alpha", subject="alpha", relation="state", object_="valid", evidence_ids=("e",))
    knowledge.add(claim)
    knowledge_temporal = mods.knowledge.TemporalKnowledgeView()
    knowledge_temporal.bind(claim, valid_from=T_2020, valid_until=T_2030)
    relations = _relations(("state", RelationCardinality.EXCLUSIVE))

    context = _context(mods, T_2025)
    scope = _scope(
        mods,
        claim_id="claim.alpha",
        context=context,
        knowledge=knowledge,
        evidence=evidence,
        relations=relations,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )
    verification = mods.verification.TemporalTruthVerificationLedger()
    receipt = _record_receipt(
        mods,
        verification,
        receipt_id="v4",
        claim_id="claim.alpha",
        evidence_id="e",
        source_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        context=context,
        scope=scope,
    )
    assert receipt.binding_mode == TEMPORAL_V4

    other_context = _context(mods, "2026-01-01T00:00:00Z")
    other_scope = _scope(
        mods,
        claim_id="claim.alpha",
        context=other_context,
        knowledge=knowledge,
        evidence=evidence,
        relations=relations,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )
    assert not verification.receipt_is_current(receipt, scope=other_scope, temporal_context=other_context)


def test_a9_temporal_assurance_binds_v4_as_of_and_revocation_invalidates():
    mods = _a9()
    evidence = EvidenceLedger()
    row = _evidence("e", claim_id="claim.alpha")
    evidence.record(row)
    evidence_temporal = mods.evidence.TemporalEvidenceView()
    evidence_temporal.bind(row, valid_from=T_2020, valid_until=T_2030)

    knowledge = KnowledgeLedger()
    claim = _claim("claim.alpha", subject="alpha", relation="state", object_="valid", evidence_ids=("e",))
    knowledge.add(claim)
    knowledge_temporal = mods.knowledge.TemporalKnowledgeView()
    knowledge_temporal.bind(claim, valid_from=T_2020, valid_until=T_2030)
    relations = _relations(("state", RelationCardinality.EXCLUSIVE))
    context = _context(mods, T_2025)
    scope = _scope(
        mods,
        claim_id="claim.alpha",
        context=context,
        knowledge=knowledge,
        evidence=evidence,
        relations=relations,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )
    verification = mods.verification.TemporalTruthVerificationLedger()
    _record_receipt(
        mods,
        verification,
        receipt_id="v4",
        claim_id="claim.alpha",
        evidence_id="e",
        source_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        context=context,
        scope=scope,
    )

    gate = mods.assurance.TemporalTruthAssuranceGate()
    certificate = gate.close(
        claim_id="claim.alpha",
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=relations,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        verification=verification,
    )
    assert certificate.closed
    assert certificate.binding_mode == TEMPORAL_V4
    assert certificate.as_of == T_2025
    assert gate.validate_certificate(
        certificate,
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=relations,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        verification=verification,
    )
    assert not gate.validate_certificate(
        certificate,
        temporal_context=_context(mods, "2026-01-01T00:00:00Z"),
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=relations,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        verification=verification,
    )

    evidence.revoke("e", reason="withdrawn")
    assert not gate.validate_certificate(
        certificate,
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=relations,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        verification=verification,
    )


def test_a9_relevant_relation_policy_revision_invalidates_temporal_certificate():
    mods = _a9()
    evidence = EvidenceLedger()
    row = _evidence("e", claim_id="claim.alpha")
    evidence.record(row)
    evidence_temporal = mods.evidence.TemporalEvidenceView()
    knowledge = KnowledgeLedger()
    claim = _claim("claim.alpha", subject="alpha", relation="status", object_="online", evidence_ids=("e",))
    knowledge.add(claim)
    knowledge_temporal = mods.knowledge.TemporalKnowledgeView()
    relations = _relations(("status", RelationCardinality.EXCLUSIVE))
    context = _context(mods, T_2025)
    scope = _scope(
        mods,
        claim_id="claim.alpha",
        context=context,
        knowledge=knowledge,
        evidence=evidence,
        relations=relations,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )
    verification = mods.verification.TemporalTruthVerificationLedger()
    _record_receipt(
        mods,
        verification,
        receipt_id="v4",
        claim_id="claim.alpha",
        evidence_id="e",
        source_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        context=context,
        scope=scope,
    )
    gate = mods.assurance.TemporalTruthAssuranceGate()
    certificate = gate.close(
        claim_id="claim.alpha",
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=relations,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        verification=verification,
    )
    assert certificate.closed

    current = relations.current("status")
    assert current is not None
    relations.record(RelationSemanticsRevision.create(
        relation="status",
        revision=2,
        cardinality=RelationCardinality.MULTI_VALUED,
        previous_digest=current.digest,
    ))
    assert not gate.validate_certificate(
        certificate,
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=relations,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        verification=verification,
    )
