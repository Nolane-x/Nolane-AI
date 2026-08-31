from __future__ import annotations

from nolane.external_core.assurance_justification_truth import JustificationTruthAssuranceGate
from nolane.external_core.evidence_provenance_truth import (
    SourceProvenanceRegistry,
    SourceProvenanceRevision,
)
from nolane.external_core.evidence_temporal_truth import TemporalEvidenceView
from nolane.external_core.evidence_truth import (
    EvidenceChannel,
    EvidenceLedger,
    EvidencePolarity,
    TruthEvidence,
)
from nolane.external_core.knowledge_justification_truth import (
    KnowledgeJustificationRegistry,
    KnowledgeJustificationRevision,
)
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_justification_truth import (
    JustificationTruthVerificationLedger,
    JustificationTruthVerificationReceipt,
)
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


def _provenance(registry: SourceProvenanceRegistry, source_id: str, controller_id: str) -> None:
    registry.register(
        SourceProvenanceRevision.create(
            source_id=source_id,
            revision=1,
            predecessor_digest="",
            controller_id=controller_id,
            parent_source_ids=(),
        )
    )


def _record(
    evidence: EvidenceLedger,
    *,
    evidence_id: str,
    claim_id: str,
    source_id: str,
    channel: EvidenceChannel = EvidenceChannel.OBSERVATION,
) -> None:
    evidence.record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=claim_id,
            source_id=source_id,
            source_family=f"legacy:{source_id}",
            channel=channel,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest=f"payload:{evidence_id}",
        )
    )


def test_a12_unsupported_parent_on_dead_alternative_does_not_veto_live_target_path():
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    provenance = SourceProvenanceRegistry()
    justifications = KnowledgeJustificationRegistry()
    relation_semantics = RelationSemanticsRegistry()
    knowledge_temporal = TemporalKnowledgeView()
    evidence_temporal = TemporalEvidenceView()
    context = TemporalContext.create(as_of=AS_OF)

    parent = knowledge.add(
        KnowledgeClaim.create(
            claim_id="dead-parent",
            subject="dead-parent",
            relation="state",
            object="unknown",
        )
    )
    target = knowledge.add(
        KnowledgeClaim.create(
            claim_id="target",
            subject="system",
            relation="safe",
            object="yes",
            risk=KnowledgeRisk.CRITICAL,
            evidence_ids=("live-target-support",),
        )
    )

    for evidence_id, source_id, controller_id in (
        ("live-target-support", "live-target-source", "live-target-controller"),
        ("dead-branch-support", "dead-branch-source", "dead-branch-controller"),
    ):
        _provenance(provenance, source_id, controller_id)
        _record(
            evidence,
            evidence_id=evidence_id,
            claim_id=target.claim_id,
            source_id=source_id,
        )

    justifications.register(
        KnowledgeJustificationRevision.create(
            justification_id="j-dead-parent-branch",
            claim=target,
            evidence_ids=("dead-branch-support",),
            parent_claim_ids=(parent.claim_id,),
        ),
        knowledge=knowledge,
    )

    verification = JustificationTruthVerificationLedger()
    channels = (
        EvidenceChannel.TEST,
        EvidenceChannel.REPRODUCTION,
        EvidenceChannel.ADVERSARIAL,
    )

    from nolane.external_core.epistemic_justification_truth import JustificationEpistemicJudge

    scope = JustificationEpistemicJudge().relation_aware_temporal_scope(
        target.claim_id,
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=relation_semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        source_provenance=provenance,
        justifications=justifications,
    )
    assert scope.justification_status("j-dead-parent-branch").status == "dead"
    assert scope.assessment(parent.claim_id).disposition.value == "unknown"
    assert scope.assessment(target.claim_id).disposition.value == "supported"

    for index, channel in enumerate(channels, start=1):
        verifier_id = f"verifier-{index}"
        verifier_evidence_id = f"verification-{index}"
        _provenance(provenance, verifier_id, f"verifier-controller-{index}")
        _record(
            evidence,
            evidence_id=verifier_evidence_id,
            claim_id=target.claim_id,
            source_id=verifier_id,
            channel=channel,
        )
        verification.record(
            JustificationTruthVerificationReceipt.create(
                receipt_id=f"receipt-{index}",
                claim_id=target.claim_id,
                verifier_id=verifier_id,
                channel=channel,
                passed=True,
                scope_digest=scope.digest,
                temporal_context_digest=context.digest,
                as_of=context.as_of,
                evidence_ids=(verifier_evidence_id,),
                source_provenance_digest=provenance.projection_digest((verifier_id,)),
            )
        )

    certificate = JustificationTruthAssuranceGate().close(
        claim_id=target.claim_id,
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=relation_semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        source_provenance=provenance,
        justifications=justifications,
        verification=verification,
    )

    assert certificate.closed is True
    assert "epistemic_lineage_not_supported" not in certificate.reasons
