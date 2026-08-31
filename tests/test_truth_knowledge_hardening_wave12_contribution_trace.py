from __future__ import annotations

from nolane.external_core.assurance_justification_truth import JustificationTruthAssuranceGate
from nolane.external_core.epistemic_justification_truth import JustificationEpistemicJudge
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


def _source(registry: SourceProvenanceRegistry, source_id: str, controller_id: str) -> None:
    registry.register(
        SourceProvenanceRevision.create(
            source_id=source_id,
            revision=1,
            predecessor_digest="",
            controller_id=controller_id,
            parent_source_ids=(),
        )
    )


def _evidence(
    ledger: EvidenceLedger,
    *,
    evidence_id: str,
    claim_id: str,
    source_id: str,
    channel: EvidenceChannel = EvidenceChannel.OBSERVATION,
) -> None:
    ledger.record(
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


def test_a12_supported_parent_on_dead_target_path_is_not_a_live_origin_exclusion():
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
            claim_id="parent-claim",
            subject="parent",
            relation="state",
            object="supported",
            evidence_ids=("parent-support",),
        )
    )
    target = knowledge.add(
        KnowledgeClaim.create(
            claim_id="target-claim",
            subject="system",
            relation="is_safe",
            object="yes",
            risk=KnowledgeRisk.CRITICAL,
            evidence_ids=("legacy-target-support",),
        )
    )

    for evidence_id, claim_id, source_id, controller_id in (
        ("parent-support", parent.claim_id, "dead-parent-source", "dead-parent-controller"),
        ("legacy-target-support", target.claim_id, "legacy-target-source", "legacy-target-controller"),
        ("live-alt-support", target.claim_id, "live-alt-source", "live-alt-controller"),
        ("dead-branch-support", target.claim_id, "dead-branch-source", "dead-branch-controller"),
    ):
        _source(provenance, source_id, controller_id)
        _evidence(
            evidence,
            evidence_id=evidence_id,
            claim_id=claim_id,
            source_id=source_id,
        )

    justifications.register(
        KnowledgeJustificationRevision.create(
            justification_id="j-live",
            claim=target,
            evidence_ids=("live-alt-support",),
        ),
        knowledge=knowledge,
    )
    justifications.register(
        KnowledgeJustificationRevision.create(
            justification_id="j-dead-with-parent",
            claim=target,
            evidence_ids=("dead-branch-support",),
            parent_claim_ids=(parent.claim_id,),
        ),
        knowledge=knowledge,
    )
    evidence.revoke("dead-branch-support", reason="dead proof branch")

    channels = (
        EvidenceChannel.TEST,
        EvidenceChannel.REPRODUCTION,
        EvidenceChannel.ADVERSARIAL,
    )
    verifier_controllers = (
        "dead-parent-controller",
        "independent-verifier-2",
        "independent-verifier-3",
    )
    for index, (controller_id, channel) in enumerate(zip(verifier_controllers, channels), start=1):
        verifier_id = f"verifier-{index}"
        evidence_id = f"verification-{index}"
        _source(provenance, verifier_id, controller_id)
        _evidence(
            evidence,
            evidence_id=evidence_id,
            claim_id=target.claim_id,
            source_id=verifier_id,
            channel=channel,
        )

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

    assert scope.justification_status("j-dead-with-parent").status == "dead"
    assert "dead-parent-source" in scope.source_ids
    assert "dead-parent-source" not in scope.supporting_source_ids

    verification = JustificationTruthVerificationLedger()
    for index, channel in enumerate(channels, start=1):
        verifier_id = f"verifier-{index}"
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
                evidence_ids=(f"verification-{index}",),
                source_provenance_digest=provenance.projection_digest((verifier_id,)),
            )
        )

    coverage = verification.coverage(
        target.claim_id,
        scope=scope,
        temporal_context=context,
        evidence=evidence,
        evidence_temporal=evidence_temporal,
        source_provenance=provenance,
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

    assert coverage.independent_source_count == 3
    assert certificate.closed is True
