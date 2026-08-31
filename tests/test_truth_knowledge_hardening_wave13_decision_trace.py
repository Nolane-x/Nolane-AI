from __future__ import annotations

from nolane.external_core.epistemic_defeasible_truth import DefeasibleEpistemicJudge
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
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger
from nolane.external_core.knowledge_undercutter_truth import (
    JustificationUndercutterRegistry,
    JustificationUndercutterRevision,
)
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_defeasible_truth import (
    DefeasibleTruthVerificationLedger,
    DefeasibleTruthVerificationReceipt,
)
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


def _prov(source_id: str, controller_id: str) -> SourceProvenanceRevision:
    return SourceProvenanceRevision.create(
        source_id=source_id,
        revision=1,
        predecessor_digest="",
        controller_id=controller_id,
        parent_source_ids=(),
    )


def _record(
    evidence: EvidenceLedger,
    *,
    evidence_id: str,
    subject_id: str,
    source_id: str,
    channel: EvidenceChannel = EvidenceChannel.OBSERVATION,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORT,
) -> None:
    evidence.record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=subject_id,
            source_id=source_id,
            source_family=f"family:{source_id}",
            channel=channel,
            polarity=polarity,
            payload_digest=f"payload:{evidence_id}",
        )
    )


def test_a13_supported_parent_of_decisive_undercutter_is_a_decision_origin():
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    semantics = RelationSemanticsRegistry()
    knowledge_temporal = TemporalKnowledgeView()
    evidence_temporal = TemporalEvidenceView()
    provenance = SourceProvenanceRegistry()
    justifications = KnowledgeJustificationRegistry()
    undercutters = JustificationUndercutterRegistry()
    context = TemporalContext.create(as_of=AS_OF)

    _record(
        evidence,
        evidence_id="target-support",
        subject_id="target",
        source_id="target-source",
    )
    provenance.register(_prov("target-source", "target-controller"))
    target = knowledge.add(
        KnowledgeClaim.create(
            claim_id="target",
            subject="system",
            relation="works",
            object="yes",
            evidence_ids=("target-support",),
        )
    )

    _record(
        evidence,
        evidence_id="parent-support",
        subject_id="attack-parent",
        source_id="parent-source",
    )
    provenance.register(_prov("parent-source", "parent-controller"))
    parent = knowledge.add(
        KnowledgeClaim.create(
            claim_id="attack-parent",
            subject="method",
            relation="is_flawed",
            object="yes",
            evidence_ids=("parent-support",),
        )
    )

    _record(
        evidence,
        evidence_id="refuting-observation",
        subject_id=target.claim_id,
        source_id="refuting-source",
        polarity=EvidencePolarity.REFUTE,
    )
    provenance.register(_prov("refuting-source", "refuting-controller"))
    refuting = justifications.register(
        KnowledgeJustificationRevision.create(
            justification_id="j-refuting",
            claim=target,
            evidence_ids=("refuting-observation",),
        ),
        knowledge=knowledge,
    )

    _record(
        evidence,
        evidence_id="attack-support",
        subject_id="u-refuting-invalid",
        source_id="attack-source",
    )
    provenance.register(_prov("attack-source", "attack-controller"))
    undercutters.register(
        JustificationUndercutterRevision.create(
            undercutter_id="u-refuting-invalid",
            claim=target,
            target_basis=refuting.basis(),
            evidence_ids=("attack-support",),
            parent_claim_ids=(parent.claim_id,),
        ),
        knowledge=knowledge,
        justifications=justifications,
    )

    provenance.register(_prov("verifier-parent", "parent-controller"))
    _record(
        evidence,
        evidence_id="verify-parent",
        subject_id=target.claim_id,
        source_id="verifier-parent",
        channel=EvidenceChannel.ADVERSARIAL,
    )

    scope = DefeasibleEpistemicJudge().relation_aware_temporal_scope(
        target.claim_id,
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        source_provenance=provenance,
        justifications=justifications,
        undercutters=undercutters,
    )

    assert scope.justification_status("j-refuting").status == "defeated"
    assert scope.assessment(target.claim_id).disposition.value == "supported"
    assert "attack-source" in scope.decision_source_ids
    assert "parent-source" in scope.decision_source_ids

    ledger = DefeasibleTruthVerificationLedger()
    ledger.record(
        DefeasibleTruthVerificationReceipt.create(
            receipt_id="r-parent-controller",
            claim_id=target.claim_id,
            verifier_id="verifier-parent",
            channel=EvidenceChannel.ADVERSARIAL,
            passed=True,
            scope_digest=scope.digest,
            temporal_context_digest=context.digest,
            as_of=context.as_of,
            evidence_ids=("verify-parent",),
            source_provenance_digest=provenance.projection_digest(("verifier-parent",)),
        )
    )
    coverage = ledger.coverage(
        target.claim_id,
        scope=scope,
        temporal_context=context,
        evidence=evidence,
        evidence_temporal=evidence_temporal,
        source_provenance=provenance,
    )

    assert coverage.independent_source_count == 0
    assert coverage.non_independent_receipt_ids == ("r-parent-controller",)
