from __future__ import annotations

from nolane.external_core.assurance_truth import TruthAssuranceGate, TruthClosureCertificate
from nolane.external_core.epistemic_truth import EpistemicJudge
from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.verification_truth import (
    RELATION_SCOPED_BINDING_MODE,
    SCOPED_BINDING_MODE,
    TruthVerificationLedger,
    TruthVerificationReceipt,
)
from nolane.memory.knowledge import RelationCardinality, RelationSemanticsRegistry, RelationSemanticsRevision


def evidence(
    evidence_id: str,
    claim_id: str,
    *,
    source: str,
    family: str,
    channel: EvidenceChannel,
) -> TruthEvidence:
    return TruthEvidence.create(
        evidence_id=evidence_id,
        subject_id=claim_id,
        source_id=source,
        source_family=family,
        channel=channel,
        polarity=EvidencePolarity.SUPPORT,
        payload_digest=f"payload:{evidence_id}",
    )


def registry_with(*rows: tuple[str, RelationCardinality]) -> RelationSemanticsRegistry:
    registry = RelationSemanticsRegistry()
    for relation, cardinality in rows:
        registry.record(RelationSemanticsRevision.create(
            relation=relation,
            revision=1,
            cardinality=cardinality,
        ))
    return registry


def add_v3_receipt(
    verification: TruthVerificationLedger,
    *,
    receipt_id: str,
    claim_id: str,
    verifier_id: str,
    family: str,
    channel: EvidenceChannel,
    evidence_ids: tuple[str, ...],
    knowledge: KnowledgeLedger,
    evidence_ledger: EvidenceLedger,
    relations: RelationSemanticsRegistry,
    passed: bool = True,
) -> TruthVerificationReceipt:
    scope = EpistemicJudge().relation_aware_dependency_scope(
        claim_id,
        knowledge=knowledge,
        evidence=evidence_ledger,
        relation_semantics=relations,
    )
    row = TruthVerificationReceipt.create(
        receipt_id=receipt_id,
        claim_id=claim_id,
        verifier_id=verifier_id,
        source_family=family,
        channel=channel,
        passed=passed,
        binding_mode=RELATION_SCOPED_BINDING_MODE,
        scope_digest=scope.digest,
        evidence_ids=evidence_ids,
    )
    return verification.record(row)


def multi_value_target(cardinality: RelationCardinality):
    ev = EvidenceLedger()
    ev.record(evidence("english-e", "claim.english", source="runner-a", family="family-a", channel=EvidenceChannel.TEST))
    ev.record(evidence("french-e", "claim.french", source="runner-b", family="family-b", channel=EvidenceChannel.REPRODUCTION))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.english", subject="alice", relation="speaks", object="English",
        risk=KnowledgeRisk.STANDARD, evidence_ids=("english-e",),
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.french", subject="alice", relation="speaks", object="French",
        risk=KnowledgeRisk.STANDARD, evidence_ids=("french-e",),
    ))
    relations = RelationSemanticsRegistry()
    if cardinality is not RelationCardinality.UNSPECIFIED:
        relations.record(RelationSemanticsRevision.create(
            relation="speaks", revision=1, cardinality=cardinality,
        ))
    verification = TruthVerificationLedger()
    add_v3_receipt(
        verification,
        receipt_id="english-v3",
        claim_id="claim.english",
        verifier_id="runner-a",
        family="family-a",
        channel=EvidenceChannel.TEST,
        evidence_ids=("english-e",),
        knowledge=knowledge,
        evidence_ledger=ev,
        relations=relations,
    )
    return knowledge, ev, relations, verification


def test_a10_multi_valued_target_can_close_with_supported_sibling_value():
    knowledge, ev, relations, verification = multi_value_target(RelationCardinality.MULTI_VALUED)
    certificate = TruthAssuranceGate().close_live(
        claim_id="claim.english",
        knowledge=knowledge,
        evidence=ev,
        verification=verification,
        relation_semantics=relations,
    )
    assert certificate.closed
    assert certificate.binding_mode == RELATION_SCOPED_BINDING_MODE
    assert certificate.is_relation_scoped
    assert certificate.verification_receipt_ids == ("english-v3",)


def test_a10_exclusive_supported_competitor_blocks_v3_closure():
    knowledge, ev, relations, verification = multi_value_target(RelationCardinality.EXCLUSIVE)
    certificate = TruthAssuranceGate().close_live(
        claim_id="claim.english",
        knowledge=knowledge,
        evidence=ev,
        verification=verification,
        relation_semantics=relations,
    )
    assert not certificate.closed
    assert certificate.binding_mode == RELATION_SCOPED_BINDING_MODE
    assert "epistemic_claim_conflicted" in certificate.reasons


def test_a10_unspecified_multiple_values_fail_closed_as_relation_semantics_ambiguity():
    knowledge, ev, relations, verification = multi_value_target(RelationCardinality.UNSPECIFIED)
    certificate = TruthAssuranceGate().close_live(
        claim_id="claim.english",
        knowledge=knowledge,
        evidence=ev,
        verification=verification,
        relation_semantics=relations,
    )
    assert not certificate.closed
    assert "relation_semantics_ambiguous" in certificate.reasons
    assert not any("conflicted" in reason for reason in certificate.reasons)


def test_a10_ancestor_relation_ambiguity_blocks_descendant_closure():
    ev = EvidenceLedger()
    ev.record(evidence("parent-a-e", "claim.parent.a", source="parent-a", family="parent-a-family", channel=EvidenceChannel.TEST))
    ev.record(evidence("parent-b-e", "claim.parent.b", source="parent-b", family="parent-b-family", channel=EvidenceChannel.ADVERSARIAL))
    ev.record(evidence("child-e", "claim.child", source="child", family="child-family", channel=EvidenceChannel.REPRODUCTION))

    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.parent.a", subject="server", relation="state", object="ready", evidence_ids=("parent-a-e",),
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.parent.b", subject="server", relation="state", object="warming", evidence_ids=("parent-b-e",),
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.child", subject="deployment", relation="depends", object="server",
        evidence_ids=("child-e",), parent_claim_ids=("claim.parent.a",),
    ))
    relations = registry_with(("depends", RelationCardinality.EXCLUSIVE))
    verification = TruthVerificationLedger()
    add_v3_receipt(
        verification,
        receipt_id="child-v3",
        claim_id="claim.child",
        verifier_id="child",
        family="child-family",
        channel=EvidenceChannel.REPRODUCTION,
        evidence_ids=("child-e",),
        knowledge=knowledge,
        evidence_ledger=ev,
        relations=relations,
    )

    certificate = TruthAssuranceGate().close_live(
        claim_id="claim.child",
        knowledge=knowledge,
        evidence=ev,
        verification=verification,
        relation_semantics=relations,
    )
    assert not certificate.closed
    assert "relation_semantics_lineage_ambiguous" in certificate.reasons


def test_a10_relevant_policy_revision_invalidates_v3_certificate_but_unrelated_revision_does_not():
    knowledge, ev, relations, verification = multi_value_target(RelationCardinality.MULTI_VALUED)
    gate = TruthAssuranceGate()
    certificate = gate.close_live(
        claim_id="claim.english", knowledge=knowledge, evidence=ev,
        verification=verification, relation_semantics=relations,
    )
    assert certificate.closed

    relations.record(RelationSemanticsRevision.create(
        relation="status", revision=1, cardinality=RelationCardinality.EXCLUSIVE,
    ))
    assert gate.validate_certificate(
        certificate,
        knowledge=knowledge,
        evidence=ev,
        verification=verification,
        relation_semantics=relations,
    )

    current = relations.current("speaks")
    assert current is not None
    relations.record(RelationSemanticsRevision.create(
        relation="speaks",
        revision=2,
        cardinality=RelationCardinality.EXCLUSIVE,
        previous_digest=current.digest,
    ))
    assert not gate.validate_certificate(
        certificate,
        knowledge=knowledge,
        evidence=ev,
        verification=verification,
        relation_semantics=relations,
    )


def test_a10_v3_history_never_downgrades_to_still_valid_v2_after_policy_change():
    ev = EvidenceLedger()
    ev.record(evidence("e1", "claim.alpha", source="runner-a", family="family-a", channel=EvidenceChannel.TEST))
    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.alpha", subject="alpha", relation="status", object="online",
        risk=KnowledgeRisk.STANDARD, evidence_ids=("e1",),
    ))
    relations = registry_with(("status", RelationCardinality.EXCLUSIVE))
    judge = EpistemicJudge()
    v2_scope = judge.dependency_scope("claim.alpha", knowledge=knowledge, evidence=ev)
    v3_scope = judge.relation_aware_dependency_scope(
        "claim.alpha", knowledge=knowledge, evidence=ev, relation_semantics=relations,
    )
    verification = TruthVerificationLedger()
    verification.record(TruthVerificationReceipt.create(
        receipt_id="v2", claim_id="claim.alpha", verifier_id="runner-a",
        source_family="family-a", channel=EvidenceChannel.TEST, passed=True,
        scope_digest=v2_scope.digest, evidence_ids=("e1",),
    ))
    verification.record(TruthVerificationReceipt.create(
        receipt_id="v3", claim_id="claim.alpha", verifier_id="runner-a",
        source_family="family-a", channel=EvidenceChannel.TEST, passed=True,
        binding_mode=RELATION_SCOPED_BINDING_MODE,
        scope_digest=v3_scope.digest, evidence_ids=("e1",),
    ))

    current = relations.current("status")
    assert current is not None
    relations.record(RelationSemanticsRevision.create(
        relation="status", revision=2, cardinality=RelationCardinality.MULTI_VALUED,
        previous_digest=current.digest,
    ))

    certificate = TruthAssuranceGate().close_live(
        claim_id="claim.alpha", knowledge=knowledge, evidence=ev,
        verification=verification, relation_semantics=relations,
    )
    assert certificate.binding_mode == RELATION_SCOPED_BINDING_MODE
    assert not certificate.closed
    assert "insufficient_independent_verification" in certificate.reasons
    assert certificate.verification_receipt_ids == ()


def test_a10_v3_certificate_validation_requires_live_relation_semantics_authority():
    knowledge, ev, relations, verification = multi_value_target(RelationCardinality.MULTI_VALUED)
    gate = TruthAssuranceGate()
    certificate = gate.close_live(
        claim_id="claim.english", knowledge=knowledge, evidence=ev,
        verification=verification, relation_semantics=relations,
    )
    assert certificate.closed
    assert not gate.validate_certificate(
        certificate, knowledge=knowledge, evidence=ev, verification=verification,
    )


def test_a10_v1_and_v2_certificate_payload_modes_remain_historical():
    v1 = TruthClosureCertificate.create(
        claim_id="claim.alpha", risk=KnowledgeRisk.LOW,
        knowledge_digest="k", evidence_digest="e", epistemic_digest="p", verification_digest="v",
        verification_receipt_ids=(), epistemic_debt_ids=(), closed=True, reasons=(),
    )
    v2 = TruthClosureCertificate.create(
        claim_id="claim.alpha", risk=KnowledgeRisk.LOW,
        binding_mode=SCOPED_BINDING_MODE,
        scope_digest="scope-v2", verification_scope_digest="verification-v2",
        verification_receipt_ids=(), epistemic_debt_ids=(), closed=True, reasons=(),
    )
    assert "binding_mode" not in v1.to_state()
    assert v2.to_state()["binding_mode"] == SCOPED_BINDING_MODE
    assert RELATION_SCOPED_BINDING_MODE not in repr(v2.to_state())
