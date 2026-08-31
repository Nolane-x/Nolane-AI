from nolane.external_core.assurance_provenance_truth import ProvenanceTruthAssuranceGate
from nolane.external_core.epistemic_provenance_truth import ProvenanceEpistemicJudge
from nolane.external_core.evidence_provenance_truth import SourceProvenanceRegistry, SourceProvenanceRevision
from nolane.external_core.evidence_temporal_truth import TemporalEvidenceView
from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_provenance_truth import ProvenanceTruthVerificationLedger, ProvenanceTruthVerificationReceipt
from nolane.memory.knowledge import RelationSemanticsRegistry


def _source(source_id: str, controller_id: str) -> SourceProvenanceRevision:
    return SourceProvenanceRevision.create(source_id=source_id, revision=1, controller_id=controller_id)


def test_a11_claim_origin_controller_cannot_count_as_independent_verification():
    context = TemporalContext.create(as_of="2026-08-31T00:00:00Z")
    evidence = EvidenceLedger()
    knowledge = KnowledgeLedger()
    relation_semantics = RelationSemanticsRegistry()
    evidence_temporal = TemporalEvidenceView()
    knowledge_temporal = TemporalKnowledgeView()
    provenance = SourceProvenanceRegistry()

    provenance.register(_source("claim-source", "claim-controller"))
    evidence.record(TruthEvidence.create(
        evidence_id="claim-support", subject_id="claim-critical", source_id="claim-source",
        source_family="legacy-claim-family", channel=EvidenceChannel.OBSERVATION,
        polarity=EvidencePolarity.SUPPORT, payload_digest="claim-support-payload",
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim-critical", subject="system", relation="is_safe", object="yes",
        risk=KnowledgeRisk.CRITICAL, evidence_ids=("claim-support",),
    ))

    verifier_rows = (
        ("verifier-origin", "claim-controller", EvidenceChannel.TEST),
        ("verifier-2", "controller-2", EvidenceChannel.REPRODUCTION),
        ("verifier-3", "controller-3", EvidenceChannel.ADVERSARIAL),
    )
    for verifier_id, controller_id, channel in verifier_rows:
        provenance.register(_source(verifier_id, controller_id))
        evidence.record(TruthEvidence.create(
            evidence_id=f"evidence-{verifier_id}", subject_id="claim-critical", source_id=verifier_id,
            source_family=f"legacy-{verifier_id}", channel=channel,
            polarity=EvidencePolarity.SUPPORT, payload_digest=f"payload-{verifier_id}",
        ))

    scope = ProvenanceEpistemicJudge().relation_aware_temporal_scope(
        "claim-critical", temporal_context=context, knowledge=knowledge, evidence=evidence,
        relation_semantics=relation_semantics, knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal, source_provenance=provenance,
    )
    verification = ProvenanceTruthVerificationLedger()
    for index, (verifier_id, _controller_id, channel) in enumerate(verifier_rows, start=1):
        verification.record(ProvenanceTruthVerificationReceipt.create(
            receipt_id=f"receipt-{index}", claim_id="claim-critical", verifier_id=verifier_id,
            channel=channel, passed=True, scope_digest=scope.digest,
            temporal_context_digest=context.digest, as_of=context.as_of,
            evidence_ids=(f"evidence-{verifier_id}",),
            source_provenance_digest=provenance.projection_digest((verifier_id,)),
        ))

    coverage = verification.coverage(
        "claim-critical", scope=scope, temporal_context=context, evidence=evidence,
        evidence_temporal=evidence_temporal, source_provenance=provenance,
    )
    certificate = ProvenanceTruthAssuranceGate().close(
        claim_id="claim-critical", temporal_context=context, knowledge=knowledge, evidence=evidence,
        relation_semantics=relation_semantics, knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal, source_provenance=provenance, verification=verification,
    )

    assert coverage.independent_source_count == 2
    assert coverage.channel_count == 3
    assert "receipt-1" in coverage.non_independent_receipt_ids
    assert certificate.closed is False
    assert "insufficient_independent_verification" in certificate.reasons
